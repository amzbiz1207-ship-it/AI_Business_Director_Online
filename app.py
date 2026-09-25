import os
import re
import html
from pathlib import Path
from datetime import datetime
from io import BytesIO

import streamlit as st
import google.generativeai as genai

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


APP_TITLE = "AI Business Director"


def load_env_key():
    """
    Безопасная загрузка Google API Key.

    Работает в трёх вариантах:
    1. Streamlit Secrets — для онлайн-публикации.
    2. Переменная окружения GOOGLE_API_KEY.
    3. Локальный файл .env.
    """

    # 1. Streamlit Secrets — для онлайн-публикации Streamlit Cloud
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            key = str(st.secrets["GOOGLE_API_KEY"]).strip()
            if key:
                return key
    except Exception:
        pass

    # 2. Переменная окружения
    env_key = os.getenv("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip()

    # 3. Локальный файл .env
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                return line.split("=", 1)[1].strip()

    return None

def load_working_model():
    model_file = Path("gemini_working_model.txt")
    if model_file.exists():
        model_name = model_file.read_text(encoding="utf-8").strip()
        if model_name:
            return model_name

    return "models/gemini-3.6-flash"


def clean_filename(name):
    name = name.strip() or "business"
    name = re.sub(r"[^\wа-яА-ЯёЁ\-]+", "_", name)
    name = name.strip("_")
    return name or "business"


def register_pdf_font():
    try:
        import urllib.request

        font_url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
        font_path = "/tmp/NotoSans-Regular.ttf"

        if not Path(font_path).exists():
            urllib.request.urlretrieve(font_url, font_path)

        pdfmetrics.registerFont(TTFont("AppFont", font_path))
        return "AppFont"

    except Exception:
        pass

    try:
        local_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        if Path(local_font).exists():
            pdfmetrics.registerFont(TTFont("AppFont", local_font))
            return "AppFont"

    except Exception:
        pass

    return "Helvetica"

def markdown_to_pdf_bytes(markdown_text, title="Пакет продвижения", service_name="AI Business Director"):
    """
    Создаёт более аккуратный PDF:
    - русские шрифты;
    - заголовки;
    - таблицы;
    - дата создания;
    - нижний колонтитул.
    """
    buffer = BytesIO()
    font_name = register_pdf_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "RussianNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6,
    )

    small = ParagraphStyle(
        "RussianSmall",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#555555"),
        spaceAfter=5,
    )

    h1 = ParagraphStyle(
        "RussianH1",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1F3A2E"),
        spaceAfter=12,
    )

    h2 = ParagraphStyle(
        "RussianH2",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#243B53"),
        spaceBefore=10,
        spaceAfter=7,
    )

    h3 = ParagraphStyle(
        "RussianH3",
        parent=styles["Heading3"],
        fontName=font_name,
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#333333"),
        spaceBefore=7,
        spaceAfter=5,
    )

    story = []

    created = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Титульный блок
    story.append(Paragraph(html.escape(title), h1))
    story.append(Paragraph(f"Создано: {created}", small))
    story.append(Paragraph(f"Подготовлено с помощью {html.escape(service_name)}", small))
    story.append(Spacer(1, 10))

    def _norm_pdf_heading(value):
        value = value.replace("#", "")
        value = value.replace("«", "").replace("»", "")
        value = value.strip().lower()
        value = re.sub(r"\s+", " ", value)
        return value

    title_norm = _norm_pdf_heading(title)
    seen_h1 = set()

    lines = markdown_text.splitlines()
    i = 0

    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Markdown bold чистим
        line = line.replace("**", "").replace("__", "")

        # Заголовки
        if line.startswith("# "):
            heading_text = line[2:].strip()
            heading_norm = _norm_pdf_heading(heading_text)

            # Главный заголовок уже есть в титульном блоке PDF.
            # Поэтому такой же заголовок из markdown не добавляем повторно.
            if heading_norm == title_norm or heading_norm in seen_h1:
                i += 1
                continue

            seen_h1.add(heading_norm)
            story.append(Paragraph(html.escape(heading_text), h1))
            i += 1
            continue

        if line.startswith("## "):
            story.append(Paragraph(html.escape(line[3:].strip()), h2))
            i += 1
            continue

        if line.startswith("### "):
            story.append(Paragraph(html.escape(line[4:].strip()), h3))
            i += 1
            continue

        # Markdown-таблица
        if "|" in line:
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                current = lines[i].strip()
                if "---" not in current:
                    table_lines.append(current)
                i += 1

            rows = []
            for table_line in table_lines:
                cells = [c.strip() for c in table_line.strip("|").split("|")]
                if cells:
                    rows.append([
                        Paragraph(html.escape(cell.replace("**", "")), small)
                        for cell in cells
                    ])

            if rows:
                col_count = max(len(r) for r in rows)
                page_width = A4[0] - 32 * mm
                col_width = page_width / max(col_count, 1)

                table = Table(
                    rows,
                    colWidths=[col_width] * col_count,
                    repeatRows=1 if len(rows) > 1 else 0,
                )

                table.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF4EF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F3A2E")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))

                story.append(table)
                story.append(Spacer(1, 8))

            continue

        # Списки
        if line.startswith("- "):
            story.append(Paragraph(html.escape("• " + line[2:].strip()), normal))
            i += 1
            continue

        # Нумерованные строки
        if re.match(r"^\d+\.\s", line):
            story.append(Paragraph(html.escape(line), normal))
            i += 1
            continue

        # Разделитель
        if line.strip() in ["---", "***"]:
            story.append(Spacer(1, 8))
            i += 1
            continue

        # Обычный текст
        story.append(Paragraph(html.escape(line), normal))
        i += 1

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#777777"))

        page_num = canvas.getPageNumber()
        footer_text = f"{service_name} • страница {page_num}"

        canvas.drawString(16 * mm, 10 * mm, footer_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer.getvalue()

def remove_english_service_words(text):
    replacements = {
        "Business Name": "Название бизнеса",
        "Niche": "Ниша",
        "Location/Format": "Локация / формат работы",
        "Target Audience": "Целевая аудитория",
        "Goal": "Цель продвижения",
        "Channels": "Каналы продвижения",
        "Advantages": "Преимущества",
        "Offer/Promo": "Оффер / акция",
        "Tone": "Тон коммуникации",
        "Extra": "Дополнительная информация",
        "Output": "Результат",
        "Constraint": "Ограничение",
        "Positioning": "Позиционирование",
        "Target Audience Segments": "Сегменты целевой аудитории",
        "Segment": "Сегмент",
        "Value": "Ценность",
        "Pain": "Боль",
        "Offer": "Оффер",
        "Pains": "Боли",
        "Desires": "Желания",
        "Objections": "Возражения",
    }

    for eng, ru in replacements.items():
        text = text.replace(eng, ru)

    return text



def clean_ai_output(text):
    """
    Дополнительная очистка результата:
    - убирает английский служебный блок до русского заголовка;
    - заменяет частые английские слова;
    - удаляет строки, похожие на черновые инструкции модели.
    """

    if not text:
        return text

    # Заменяем случайные английские "Day 1 / Day 7" на русские "День 1 / День 7"
    text = re.sub(r"\b[Dd]ay\s+(\d+)\s*:", r"День \1:", text)

    # Если модель вывела служебный английский текст ДО нормального русского заголовка,
    # отрезаем всё, что было до "# Пакет продвижения..."
    marker = "# Пакет продвижения"
    idx = text.find(marker)
    if idx > 0:
        text = text[idx:].lstrip()

    # Если заголовок есть без решётки
    marker2 = "Пакет продвижения для бизнеса"
    idx2 = text.find(marker2)
    if idx2 > 0 and idx2 < 1500:
        text = "# " + text[idx2:].lstrip()

    replacements = {
        "Reels idea example": "Пример идеи для Reels",
        "Message template example": "Пример сообщения клиенту",
        "Target audience refinement": "Уточнение целевой аудитории",
        "Formatting": "Форматирование",
        "Use Markdown headers correctly": "Используй корректные заголовки Markdown",
        "Proceeding to generate the full Russian text following the structure": "",
        "Topic": "Тема",
        "Script": "Сценарий",
        "Common tax mistake": "Типичная налоговая ошибка",
        "Price": "Цена",
        "Freelancers": "фрилансеры",
        "SME": "малый и средний бизнес",
        "Entrepreneurs": "предприниматели",
        "Business": "Бизнес",
        "Marketing": "Маркетинг",
        "Content": "Контент",
        "Customer": "Клиент",
        "Customers": "Клиенты",
        "Sales": "Продажи",
        "Promotion": "Продвижение",
        "Plan": "План",
        "Strategy": "Стратегия",
        "Template": "Шаблон",
        "Example": "Пример",
    }

    for eng, ru in replacements.items():
        text = text.replace(eng, ru)

    # Удаляем строки, которые выглядят как служебные англоязычные инструкции модели
    bad_phrases = [
        "proceeding to generate",
        "use markdown headers",
        "reels idea example",
        "message template example",
        "target audience refinement",
        "formatting:",
        "common tax mistake",
    ]

    cleaned_lines = []

    for line in text.splitlines():
        low = line.lower()

        if any(phrase in low for phrase in bad_phrases):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Убираем повторяющиеся одинаковые заголовки, особенно "Пакет продвижения..."
    cleaned = []
    seen_main_titles = set()
    last_heading_norm = None

    def _norm_heading(value):
        value = value.replace("#", "")
        value = value.replace("«", "").replace("»", "")
        value = value.strip().lower()
        value = re.sub(r"\s+", " ", value)
        return value

    for line in text.splitlines():
        stripped = line.strip()
        visible = stripped.replace("#", "").strip()
        norm = _norm_heading(stripped)

        # Если главный заголовок повторился — оставляем только первый
        if stripped.startswith("#") and "Пакет продвижения для бизнеса" in visible:
            if norm in seen_main_titles:
                continue
            seen_main_titles.add(norm)

        # Если подряд идут одинаковые заголовки — второй убираем
        if stripped.startswith("#") and norm and norm == last_heading_norm:
            continue

        cleaned.append(line)

        if stripped.startswith("#") and norm:
            last_heading_norm = norm

    text = "\n".join(cleaned)

    # Русифицируем частые англоязычные названия форматов
    text = re.sub(r"\bReels\b", "короткие видео", text)
    text = re.sub(r"\breels\b", "короткие видео", text)
    text = re.sub(r"\bStories\b", "сторис", text)
    text = re.sub(r"\bstories\b", "сторис", text)
    text = re.sub(r"\bStory\b", "сторис", text)
    text = re.sub(r"\bstory\b", "сторис", text)

    # Чистим возможные неловкие повторы после замены
    text = text.replace("Идеи для короткие видео / коротких видео", "Идеи для коротких видео")
    text = text.replace("Идеи для короткие видео", "Идеи для коротких видео")
    text = text.replace("Короткие видео / коротких видео", "Короткие видео")
    text = text.replace("короткие видео / коротких видео", "короткие видео")

    # Красивые заголовки таблиц
    text = text.replace("| короткие видео | сторис |", "| Короткое видео | Сторис |")
    text = text.replace("| Короткие видео | сторис |", "| Короткое видео | Сторис |")
    text = text.replace("| Короткие видео | Сторис |", "| Короткое видео | Сторис |")

    # Убираем лишние пустые строки подряд
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def generate_business_package(data):
    api_key = load_env_key()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY не найден в файле .env")

    model_name = load_working_model()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""
Ты — профессиональный русскоязычный маркетолог, стратег по продвижению малого бизнеса,
контент-директор и специалист по упаковке офферов.

ТВОЯ ЗАДАЧА:
Создать подробный, практичный и готовый к использованию пакет продвижения
для конкретного бизнеса.

СТРОГИЕ ПРАВИЛА ЯЗЫКА:
- Пиши ТОЛЬКО на русском языке.
- Не используй английские заголовки.
- Не используй английские служебные слова: Business Name, Niche, Goal, Channels, Target Audience, Output, Constraint.
- Даже если часть анкеты написана на английском, итоговый ответ должен быть полностью на русском.
- Можно оставлять только названия платформ: Instagram, TikTok, Telegram, Pinterest. Форматы Reels и Stories пиши по-русски: «короткие видео» и «сторис».
- Все разделы, таблицы, шаблоны сообщений и пояснения должны быть на русском языке.

ВАЖНО:
- Не пиши рассуждения о том, как ты думаешь.
- Не показывай внутренний анализ.
- Не добавляй английский пересказ анкеты.
- Не предлагай купить платформу или приложение.
- Все офферы, сообщения, сторис и идеи должны относиться только к бизнесу клиента.
- Пиши конкретно под указанную нишу.
- Избегай общих фраз.
- Давай готовые формулировки, которые можно сразу использовать.
- Стиль: ясный, профессиональный, понятный владельцу малого бизнеса.

ДАННЫЕ БИЗНЕСА:

Название бизнеса:
{data["business_name"]}

Тип бизнеса / ниша:
{data["business_type"]}

Город / локация / формат работы:
{data["location"]}

Что продаёт бизнес:
{data["products"]}

Для кого этот бизнес:
{data["audience"]}

Главная цель продвижения:
{data["goal"]}

Каналы продвижения:
{data["channels"]}

Особенности / преимущества:
{data["advantages"]}

Акция / оффер:
{data["offer"]}

Тон коммуникации:
{data["tone"]}

Дополнительная информация:
{data["extra"]}

СОЗДАЙ ОТВЕТ СТРОГО В ЭТОМ ФОРМАТЕ:

# Пакет продвижения для бизнеса «{data["business_name"]}»

## 1. Краткое позиционирование
Опиши, как бизнес должен звучать для клиента: кто мы, для кого, какую проблему решаем.

## 2. Целевая аудитория
Раздели аудиторию на 3–5 сегментов. Для каждого сегмента напиши:
- кто это;
- что ему важно;
- какие у него боли;
- что ему предложить.

## 3. Основные боли, желания и возражения клиентов
Сделай списки:
- боли;
- страхи;
- желания;
- возражения.

## 4. Сильные офферы
Дай 7–10 готовых офферов для этого бизнеса.

## 5. Идеи для коротких видео
Дай 15 идей. Для каждой идеи напиши:
- тема;
- короткий сценарий;
- первая фраза для начала видео.

## 6. Идеи для Stories
Дай 15 идей для сторис:
- прогрев;
- доверие;
- продажи;
- отзывы;
- закулисье;
- вопросы-ответы.

## 7. Идеи для постов
Дай 10 тем постов с коротким описанием.

## 8. Готовые тексты сообщений клиентам
Сделай шаблоны:
- первое сообщение;
- ответ на вопрос о цене;
- ответ на сомнение;
- приглашение к покупке или записи;
- сообщение после покупки или услуги;
- просьба оставить отзыв.

## 9. Контент-план на 7 дней
Сделай таблицу:
День | Короткое видео | Сторис | Пост или действие | Цель

## 10. Мини-воронка продаж
Опиши путь клиента:
увидел контент → заинтересовался → написал → получил предложение → купил или записался.

## 11. Что улучшить в упаковке
Дай рекомендации по:
- шапке профиля;
- закреплённым сторис;
- визуалу;
- описанию услуг;
- отзывам;
- призыву к действию.

## 12. Итоговый план действий на ближайшие 7 дней
Дай простой чек-лист по дням.

Формат ответа: Markdown.
Пиши только готовый результат.
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.6,
            "max_output_tokens": 8192,
        },
    )

    result = response.text
    result = remove_english_service_words(result)
    result = clean_ai_output(result)

    return result, model_name

_generate_business_package_ru = generate_business_package


def generate_business_package(data):
    output_language = data.get("output_language", "Русский")

    if output_language != "English":
        return _generate_business_package_ru(data)

    api_key = load_env_key()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY не найден")

    model_name = load_working_model()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""
You are a professional English-speaking marketing strategist, business growth advisor,
content director, and offer packaging specialist.

YOUR TASK:
Create a detailed, practical, ready-to-use business promotion package for the specific business.

STRICT LANGUAGE RULES:
- Write ONLY in English.
- Do not use Russian headings.
- Do not include Russian text.
- Do not include internal reasoning.
- Do not explain how you think.
- Do not add a translation.
- All sections, tables, message templates, and recommendations must be in English.
- Be specific to the client's niche.
- Avoid generic phrases.
- Give ready-to-use wording.

BUSINESS DATA:

Business name:
{data['business_name']}

Business type / niche:
{data['business_type']}

Location / format:
{data['location']}

Products or services:
{data['products']}

Target audience:
{data['audience']}

Main promotion goal:
{data['goal']}

Promotion channels:
{data['channels']}

Strengths / advantages:
{data['advantages']}

Offer / promotion:
{data['offer']}

Tone of voice:
{data['tone']}

Additional information:
{data['extra']}

CREATE THE RESPONSE STRICTLY IN THIS FORMAT:

# Business promotion package for "{data['business_name']}"

## 1. Brief positioning
Describe how the business should sound to customers: who we are, who we help, and what problem we solve.

## 2. Target audience
Divide the audience into 3–5 segments. For each segment write:
- who they are;
- what matters to them;
- their pain points;
- what to offer them.

## 3. Main customer pain points, desires, and objections
Create lists:
- pain points;
- fears;
- desires;
- objections.

## 4. Strong offers
Give 7–10 ready-to-use offers for this business.

## 5. Short video ideas
Give 15 ideas. For each idea write:
- topic;
- short script;
- opening hook.

## 6. Stories ideas
Give 15 ideas for stories:
- warming up;
- trust building;
- sales;
- reviews;
- behind the scenes;
- Q&A.

## 7. Post ideas
Give 10 post topics with short descriptions.

## 8. Ready-to-use client message templates
Create templates:
- first message;
- reply to a price question;
- reply to hesitation;
- invitation to buy or book;
- message after purchase or service;
- request for a review.

## 9. 7-day content plan
Create a table:
Day | Short video | Stories | Post or action | Goal

## 10. Mini sales funnel
Describe the customer journey:
saw content → became interested → sent a message → received an offer → bought or booked.

## 11. What to improve in business packaging
Give recommendations for:
- profile bio;
- pinned stories/highlights;
- visuals;
- service description;
- reviews;
- call to action.

## 12. 7-day action plan
Give a simple day-by-day checklist.

Response format: Markdown.
Write only the final result.
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.6,
            "max_output_tokens": 8192,
        },
    )

    result = response.text.strip()

    return result, model_name
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        display: none;
    }
    [data-testid="collapsedControl"] {
        display: none;
    }
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🤖 AI Business Director")
st.caption("ИИ-сервис для роста бизнеса, маркетинга и продвижения")

st.markdown(
    """
    <div style="
        padding: 18px 22px;
        border-radius: 16px;
        background: linear-gradient(135deg, #eef7f1 0%, #f8fbff 100%);
        border: 1px solid #dfeee5;
        margin-bottom: 22px;
    ">
        <h3 style="margin-top:0; color:#1F3A2E;">
            Создайте стратегию продвижения и роста бизнеса за несколько минут
        </h3>
        <p style="font-size:16px; margin-bottom:0; color:#334155;">
            Заполните короткую анкету — система подготовит позиционирование,
            офферы, идеи для контента, сообщения клиентам, мини-воронку продаж,
            контент-план и рекомендации по упаковке бизнеса. Результат можно
            скачать в PDF, Markdown или TXT.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

api_key = load_env_key()
working_model = load_working_model()

if not api_key:
    st.error("GOOGLE_API_KEY не найден. Для локального запуска проверьте файл .env, для онлайн-версии — Streamlit Secrets.")

st.subheader("1. Заполните анкету бизнеса")

with st.form("business_form"):
    service_name = st.text_input(
        "Название сервиса / бренда для PDF",
        value="AI Business Director",
        placeholder="Например: AI Business Director"
    )

    st.caption("Это название появится в PDF в строке «Подготовлено с помощью ...».")
    output_language = st.selectbox(
        "Язык результата / Output language",
        ["Русский", "English"],
        index=0,
    )
    labels = {
        "business_name": "Business name" if output_language == "English" else "Название бизнеса",
        "business_name_ph": "Example: beauty salon, coffee shop, or toy store" if output_language == "English" else "Например: салон красоты, кофейня или магазин игрушек",
        "business_type": "Business type / niche" if output_language == "English" else "Тип бизнеса / ниша",
        "business_type_ph": "Example: handmade plush toys" if output_language == "English" else "Например: изготовление мягких игрушек ручной работы",
        "location": "City / location / work format" if output_language == "English" else "Город / локация / формат работы",
        "location_ph": "Example: online, Instagram, Etsy, Moscow" if output_language == "English" else "Например: онлайн, Instagram, Etsy, Москва",
        "products": "What do you sell?" if output_language == "English" else "Что продаёте",
        "products_ph": "Example: plush toys, keychains, gift sets, custom orders" if output_language == "English" else "Например: мягкие игрушки, брелоки, подарочные наборы, индивидуальные заказы",
        "audience": "Who is this business for?" if output_language == "English" else "Для кого этот бизнес",
        "audience_ph": "Example: parents of children aged 3–7, gift buyers, collectors" if output_language == "English" else "Например: родители детей 3–7 лет, покупатели подарков, коллекционеры",
        "goal": "Main promotion goal" if output_language == "English" else "Главная цель продвижения",
        "goal_ph": "Example: get more orders through Instagram" if output_language == "English" else "Например: больше заказов через Instagram", 
        "channels": "Promotion channels" if output_language == "English" else "Каналы продвижения",
        "channels_ph": "Example: Instagram, short videos, stories, TikTok, Telegram" if output_language == "English" else "Например: Instagram, короткие видео, сторис, TikTok, Telegram",
        "advantages": "Features / advantages" if output_language == "English" else "Особенности / преимущества",
        "advantages_ph": "Example: handmade, unique design, fast shipping, beautiful packaging" if output_language == "English" else "Например: ручная работа, уникальный дизайн, быстрая отправка, красивая упаковка",
        "offer": "Promotion / offer, if any" if output_language == "English" else "Акция / оффер, если есть",
        "offer_ph": "Example: buy two toys and get the second one 50% off" if output_language == "English" else "Например: при покупке двух игрушек вторая со скидкой 50%",
        "tone": "Tone of communication" if output_language == "English" else "Тон коммуникации",
        "tone_warm": "Warm and friendly" if output_language == "English" else "Тёплый и дружелюбный",
        "tone_expert": "Expert" if output_language == "English" else "Экспертный",
        "tone_premium": "Premium" if output_language == "English" else "Премиальный",
        "tone_light": "Light and emotional" if output_language == "English" else "Лёгкий и эмоциональный",
        "extra": "Additional information" if output_language == "English" else "Дополнительная информация",
        "extra_ph": "Any details: prices, timelines, competitors, preferences, what you have already tried..." if output_language == "English" else "Любые детали: цены, сроки, конкуренты, пожелания, что уже пробовали...",
        "submit_button": "🚀 Create an AI promotion package" if output_language == "English" else "🚀 Создать пакет продвижения через ИИ",
        "err_required": "Please fill in at least: business type and what you sell." if output_language == "English" else "Заполните минимум: тип бизнеса и что продаёте.",
        "err_api_key": "GOOGLE_API_KEY was not found. For local launch, check the .env file; for the online version, check Streamlit Secrets." if output_language == "English" else "GOOGLE_API_KEY не найден. Для локального запуска проверьте файл .env, для онлайн-версии — Streamlit Secrets.",
    }
               
    col1, col2 = st.columns(2)

    with col1:
        business_name = st.text_input(
            labels["business_name"],
            placeholder=labels["business_name_ph"]
        )

        business_type = st.text_input(
            labels["business_type"],
            placeholder=labels["business_type_ph"]
        )

        location = st.text_input(
            labels["location"],
           placeholder=labels["location_ph"]
        )

        products = st.text_area(
            labels["products"],
            placeholder=labels["products_ph"],
            height=120,
        )

        audience = st.text_area(
            labels["audience"],
            placeholder=labels["audience_ph"],
            height=120,
        )

    with col2:
        goal = st.text_area(
            labels["goal"],
            placeholder=labels["goal_ph"],
            height=100,
        )

        channels = st.text_input(
            labels["channels"],
            placeholder=labels["channels_ph"]
        )

        advantages = st.text_area(
            labels["advantages"],
            placeholder=labels["advantages_ph"],
            height=100,
        )

        offer = st.text_area(
            labels["offer"],
            placeholder=labels["offer_ph"],
            height=90,
        )

        tone = st.selectbox(
           labels["tone"],
            [
               labels["tone_warm"],
               labels["tone_expert"],
               labels["tone_premium"],
               labels["tone_light"],
            ],
        )

    extra = st.text_area(
        labels["extra"],
        placeholder=labels["extra_ph"],
        height=100,
    )

   submitted = st.form_submit_button(labels["submit_button"])
if submitted:
    if not business_type.strip() or not products.strip():
        st.error(labels["err_required"])
    elif not api_key:
        st.error(labels["err_api_key"])
    else:
        data = {
            "business_name": business_name.strip() or "Без названия",
            "business_type": business_type.strip(),
            "location": location.strip() or "Не указано",
            "products": products.strip(),
            "audience": audience.strip() or "Не указано",
            "goal": goal.strip() or "Не указано",
            "channels": channels.strip() or "Не указано",
            "advantages": advantages.strip() or "Не указано",
            "offer": offer.strip() or "Не указано",
            "tone": tone.strip(),
            "extra": extra.strip() or "Не указано",
            "service_name": service_name.strip() or "AI Business Director",
            "output_language": output_language,
        }

        with st.spinner("ИИ анализирует бизнес и создаёт пакет продвижения..."):
            try:
                result, used_model = generate_business_package(data)

                st.success("Готово! Пакет продвижения создан.")

                st.subheader("2. Готовый пакет продвижения")
                st.markdown(result)

                now = datetime.now().strftime("%Y-%m-%d_%H-%M")
                safe_name = clean_filename(data["business_name"])

                filename_md = f"paket_prodvizheniya_{safe_name}_{now}.md"
                filename_txt = f"paket_prodvizheniya_{safe_name}_{now}.txt"
                filename_pdf = f"paket_prodvizheniya_{safe_name}_{now}.pdf"

                pdf_bytes = markdown_to_pdf_bytes(
                    result,
                    title=f"Пакет продвижения для бизнеса «{data['business_name']}»",
                    service_name=data["service_name"]
                )

                st.subheader("3. Скачать результат")

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    st.download_button(
                        label="⬇️ Скачать PDF",
                        data=pdf_bytes,
                        file_name=filename_pdf,
                        mime="application/pdf",
                    )

                with col_b:
                    st.download_button(
                        label="⬇️ Скачать Markdown",
                        data=result.encode("utf-8"),
                        file_name=filename_md,
                        mime="text/markdown",
                    )

                with col_c:
                    st.download_button(
                        label="⬇️ Скачать TXT",
                        data=result.encode("utf-8"),
                        file_name=filename_txt,
                        mime="text/plain",
                    )


            except Exception as e:
                st.error("Ошибка при генерации через ИИ")
                st.exception(e)


st.divider()

with st.expander("Как пользоваться"):
    st.markdown(
        """
1. Введите название сервиса для PDF или оставьте AI Business Director.
2. Заполните анкету бизнеса.
3. Нажмите **«Создать пакет продвижения через ИИ»**.
4. Проверьте результат.
5. Скачайте PDF, Markdown или TXT.
"""
    )
