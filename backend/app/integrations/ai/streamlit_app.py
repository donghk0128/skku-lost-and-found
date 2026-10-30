"""Standalone Streamlit UI for testing AI-assisted post drafting."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from core.providers import ProviderError, provider_error_message
from core.schemas import CATEGORY_LABELS, DraftRequest, PostDraft, parse_optional_date, parse_optional_time
from core.service import create_provider, create_vision_provider, generate_draft


def estimate_cost(model_name: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """Estimate request cost from the dated local pricing snapshot."""
    pricing = json.loads((Path(__file__).parent / "evals" / "pricing.json").read_text(encoding="utf-8"))
    model_price = pricing["models"].get(model_name)
    if model_price is None or input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * model_price["input"] + output_tokens * model_price["output"]) / pricing["unit_tokens"]


st.set_page_config(
    page_title="SKKU Lost & Found AI Draft / 성균관대 분실물 AI 초안",
    page_icon="🔎",
    layout="centered",
)
st.title("Lost & Found AI Post Draft / 분실물 게시글 AI 초안")
st.caption(
    "Standalone model-evaluation prototype. It is not connected to the production database or backend, "
    "and does not save inputs or results. / 모델 평가용 독립 프로토타입이며, 운영 DB·백엔드와 연결되지 않고 "
    "입력과 결과를 저장하지 않습니다."
)

with st.sidebar:
    st.header("Model Settings / 모델 설정")
    provider_name = st.selectbox("Provider / 제공자", ["ollama", "openai"])
    default_models = {
        "ollama": ["llama3.2:3b", "llama3.2:1b"],
        "openai": ["gpt-6-luna", "gpt-6.1-sol"],
    }
    model = st.selectbox("Model / 모델", default_models[provider_name], accept_new_options=True)
    vision_models = {
        "ollama": ["moondream", "gemma3:4b"],
        "openai": ["gpt-5.2", "gpt-5-mini"],
    }
    vision_model = st.selectbox(
        "Vision Model / 비전 모델",
        vision_models[provider_name],
        accept_new_options=True,
        help="Used only for photo attribute extraction. / 사진 속성 추출에만 사용합니다.",
    )
    if provider_name == "ollama":
        st.info("Run `ollama serve` and `ollama pull llama3.2:3b` first. / 먼저 해당 명령을 실행하세요.")
    else:
        st.info("Set `OPENAI_API_KEY` in `.env`. / `.env`에 API 키를 설정하세요.")

post_type_label = st.radio(
    "Post Type / 게시글 종류", ["Lost / 분실했어요", "Found / 습득했어요"], horizontal=True
)
post_type = "LOST" if post_type_label.startswith("Lost") else "FOUND"
reference_time = st.text_input(
    "Reference Time / 기준 시각",
    value=datetime.now().astimezone().replace(microsecond=0).isoformat(),
    help="ISO 8601 timestamp with a timezone for relative-time interpretation. / 상대 시간 해석용 시각입니다.",
)
natural_language = st.text_area(
    "Describe the Situation / 상황을 자연어로 설명하세요",
    height=150,
    placeholder="Example / 예: 어제 오후 3시쯤 삼성학술정보관 2층에서 검은색 이어폰을 잃어버렸어요.",
)
uploaded_photos = st.file_uploader(
    "Photos (Optional) / 사진 첨부 (선택)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help=(
        "Lost and found reports may attach up to 5 images, 5 MiB each. Images are previewed only and are not "
        "yet analyzed. / 분실·습득 모두 최대 5장, 장당 5MiB까지 첨부할 수 있습니다. 현재는 미리보기만 제공합니다."
    ),
)
valid_photos = uploaded_photos[:5]
photo_errors: list[str] = []
if len(uploaded_photos) > 5:
    photo_errors.append("You may attach up to 5 photos. / 사진은 최대 5장까지 첨부할 수 있습니다.")
for photo in valid_photos:
    if photo.size > 5 * 1024 * 1024:
        photo_errors.append(f"{photo.name}: File exceeds 5 MiB. / 파일 크기가 5MiB를 초과합니다.")
if photo_errors:
    for message in photo_errors:
        st.error(message)
elif valid_photos:
    st.image([photo.getvalue() for photo in valid_photos], caption=[photo.name for photo in valid_photos], width=160)
    st.caption(
        f"{len(valid_photos)} photo(s) selected. A photo is sent only when image analysis is requested. / "
        f"사진 {len(valid_photos)}장이 선택되었습니다. 사진 분석을 요청할 때만 선택 사진을 전송합니다."
    )

st.subheader("Image Attribute Extraction / 사진 속성 추출")
st.caption(
    "Select one uploaded photo and extract only visible item attributes. The image is sent to the selected "
    "vision provider only when you press the button. / 첨부 사진 한 장을 선택해 눈에 보이는 물품 속성만 "
    "추출합니다. 버튼을 누를 때만 선택한 비전 provider로 전송됩니다."
)
selected_photo = None
if valid_photos and not photo_errors:
    selected_name = st.selectbox(
        "Photo to Analyze / 분석할 사진",
        [photo.name for photo in valid_photos],
    )
    selected_photo = next(photo for photo in valid_photos if photo.name == selected_name)

if st.button(
    "Extract Attributes from Photo / 사진에서 속성 추출",
    use_container_width=True,
    disabled=selected_photo is None or bool(photo_errors),
):
    vision_started = time.perf_counter()
    try:
        with st.spinner(f"Analyzing with {vision_model}... / {vision_model}로 사진을 분석하고 있습니다..."):
            vision_result = create_vision_provider(provider_name, vision_model).analyze(
                selected_photo.getvalue(), selected_photo.type
            )
        st.session_state["vision_result"] = vision_result.model_dump(mode="json")
        st.session_state["vision_result"]["wall_duration_seconds"] = time.perf_counter() - vision_started
        st.session_state["vision_photo_name"] = selected_photo.name
    except ProviderError as error:
        st.error(
            f"{provider_error_message(error)} / Vision provider error: {error.kind} "
            f"({time.perf_counter() - vision_started:.2f} sec / 초)"
        )

if "vision_result" in st.session_state:
    vision_result = st.session_state["vision_result"]
    st.markdown("#### Extracted Attributes / 추출된 속성")
    st.caption(f"Source / 분석 사진: {st.session_state['vision_photo_name']}")
    vision_columns = st.columns(3)
    vision_columns[0].metric(
        "Analysis Time / 분석 시간", f"{vision_result['wall_duration_seconds']:.2f} sec"
    )
    vision_columns[1].metric(
        "Input Tokens / 입력 토큰", vision_result["usage"]["input_tokens"] or "Unavailable / 측정 불가"
    )
    vision_columns[2].metric(
        "Output Tokens / 출력 토큰", vision_result["usage"]["output_tokens"] or "Unavailable / 측정 불가"
    )
    st.json(vision_result["attributes"])
    vision_export = {
        "photo_name": st.session_state["vision_photo_name"],
        **vision_result,
        "estimated_cost_usd": estimate_cost(
            vision_result["model"],
            vision_result["usage"]["input_tokens"],
            vision_result["usage"]["output_tokens"],
        ),
    }
    st.download_button(
        "Download Image Analysis JSON / 사진 분석 JSON 다운로드",
        data=json.dumps(vision_export, ensure_ascii=False, indent=2),
        file_name="image_attributes.json",
        mime="application/json",
        use_container_width=True,
    )

st.divider()
st.subheader("Text-to-Post Draft / 자연어 게시글 초안")

if st.button(
    "Generate AI Draft / AI로 초안 만들기",
    type="primary",
    use_container_width=True,
    disabled=bool(photo_errors),
):
    started = time.perf_counter()
    try:
        request = DraftRequest(
            post_type=post_type,
            natural_language=natural_language,
            reference_time=datetime.fromisoformat(reference_time),
        )
        with st.spinner(f"Generating with {model}... / {model}로 초안을 생성하고 있습니다..."):
            result = generate_draft(create_provider(provider_name, model), request)
        st.session_state["generation_result"] = result.model_dump(mode="json")
        st.session_state["generation_result"]["wall_duration_seconds"] = time.perf_counter() - started
        st.session_state["draft"] = result.draft.model_dump(mode="json")
    except ValidationError as error:
        st.error(f"Check the input. / 입력을 확인해 주세요: {error.errors()[0]['msg']}")
    except ValueError:
        st.error("Reference time must include a timezone. / 기준 시각은 timezone을 포함해야 합니다.")
    except ProviderError as error:
        st.error(
            f"{provider_error_message(error)} / Provider error: {error.kind} "
            f"({time.perf_counter() - started:.2f} sec / 초)"
        )

if "draft" in st.session_state:
    st.divider()
    st.subheader("Review and Edit Draft / 초안 검토 및 수정")
    draft = st.session_state["draft"]
    result_meta = st.session_state["generation_result"]
    metric_columns = st.columns(3)
    metric_columns[0].metric("Generation Time / 생성 시간", f"{result_meta['wall_duration_seconds']:.2f} sec")
    metric_columns[1].metric(
        "Input Tokens / 입력 토큰", result_meta["usage"]["input_tokens"] or "Unavailable / 측정 불가"
    )
    metric_columns[2].metric(
        "Output Tokens / 출력 토큰", result_meta["usage"]["output_tokens"] or "Unavailable / 측정 불가"
    )

    title = st.text_input("Title / 제목", value=draft["title"])
    description = st.text_area("Description / 설명", value=draft["description"], height=140)
    item_name = st.text_input("Item Name / 물품명", value=draft.get("item_name") or "")
    category_codes = list(CATEGORY_LABELS)
    current_category = draft["category_code"]
    category_code = st.selectbox(
        "Category / 카테고리",
        category_codes,
        index=category_codes.index(current_category),
        format_func=lambda code: f"{CATEGORY_LABELS[code]} ({code})",
    )
    location_text = st.text_input("Location / 장소", value=draft.get("location_text") or "")
    start_date = st.text_input("Event Start Date / 발생 시작 날짜", value=draft.get("event_start_date") or "")
    end_date = st.text_input("Event End Date / 발생 종료 날짜", value=draft.get("event_end_date") or "")
    start_time = st.text_input("Event Start Time / 발생 시작 시각 (선택)", value=draft.get("event_start_time") or "")
    end_time = st.text_input("Event End Time / 발생 종료 시각 (선택)", value=draft.get("event_end_time") or "")
    precision_options = [None, "DATE_ONLY", "EXACT", "APPROXIMATE", "RANGE"]
    current_precision = draft.get("time_precision")
    time_precision = st.selectbox(
        "Time Precision / 시각 정밀도",
        precision_options,
        index=precision_options.index(current_precision),
    )
    keywords_text = st.text_input("Keywords / 키워드", value=", ".join(draft.get("keywords", [])))
    missing_fields = st.multiselect(
        "Missing Fields / 누락 필드",
        ["item_name", "location", "event_time"],
        default=draft.get("missing_fields", []),
    )
    warnings_text = st.text_area("Warnings / 주의사항", value="\n".join(draft.get("warnings", [])))

    try:
        edited = PostDraft(
            title=title,
            description=description,
            item_name=item_name.strip() or None,
            category_code=category_code,
            location_text=location_text.strip() or None,
            event_start_date=parse_optional_date(start_date),
            event_end_date=parse_optional_date(end_date),
            event_start_time=parse_optional_time(start_time),
            event_end_time=parse_optional_time(end_time),
            time_precision=time_precision,
            keywords=[value.strip() for value in keywords_text.split(",") if value.strip()],
            missing_fields=missing_fields,
            warnings=[value.strip() for value in warnings_text.splitlines() if value.strip()],
        )
        photo_metadata = [
            {"name": photo.name, "content_type": photo.type, "size_bytes": photo.size} for photo in valid_photos
        ]
        export = {"post_type": post_type, **edited.model_dump(mode="json"), "photos": photo_metadata}
        st.success("The draft matches the post schema. / 현재 초안이 게시글 스키마를 만족합니다.")
        with st.expander("JSON Preview / JSON 미리보기"):
            st.json(export)
        st.download_button(
            "Download Edited Draft JSON / 수정한 초안 JSON 다운로드",
            data=json.dumps(export, ensure_ascii=False, indent=2),
            file_name="post_draft.json",
            mime="application/json",
            use_container_width=True,
        )
    except (ValidationError, ValueError) as error:
        st.error(f"Check the edited draft. / 수정한 초안을 확인해 주세요: {error}")

    with st.expander("Model Metrics / 모델 측정 정보"):
        cost = estimate_cost(
            result_meta["model"], result_meta["usage"]["input_tokens"], result_meta["usage"]["output_tokens"]
        )
        st.json(
            {
                "provider": result_meta["provider"],
                "model": result_meta["model"],
                **result_meta["usage"],
                "total_wall_duration_seconds": result_meta["wall_duration_seconds"],
                "estimated_cost_usd": cost,
            }
        )
