"""App settings, loaded once from ai_app/.env at import time (pydantic-settings)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
AI_DIR = APP_DIR.parent                          # ai_app/
PROJECT_ROOT = AI_DIR.parent                     # RDPR POC/
SEMANTIC_DIR = PROJECT_ROOT / "semantic"
SEMANTIC_LAYER_PATH = SEMANTIC_DIR / "semantic_layer.json"
EXAMPLE_QUERIES_PATH = SEMANTIC_DIR / "example_queries.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "DB" / "rdpr_star.sqlite"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(AI_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # Internal OpenAI-compatible vLLM gateway. Without these the app still runs: every route that does not need the
    # model (dashboard, verified answers, single-metric lookups, glossary, capability notes) works offline.
    sql_verify_model: str = ""
    sql_verify_base_url: str = ""
    sql_verify_api_key: str = ""
    ai_model_ca_bundle_path: str = ""
    llm_max_tokens: int = 2048
    llm_timeout_seconds: float = 180.0
    llm_enable_thinking: bool = False

    rdpr_db_path: str = ""
    rdpr_query_timeout_seconds: float = 60.0
    rdpr_max_rows: int = 200
    rdpr_prompt_token_budget: int = 20000
    rdpr_show_technical_details: bool = False
    rdpr_rate_limit_per_minute: int = 60
    rdpr_max_concurrent_questions: int = 8
    rdpr_queue_wait_seconds: float = 20.0
    rdpr_max_request_bytes: int = 16384
    # read-only connections in the pool: dashboard builds, reports and chat questions run side by side
    rdpr_db_connections: int = 4
    # how long a kept chat answer stays downloadable as an Excel report
    rdpr_report_ttl_seconds: int = 3 * 3600
    # Second model pass that reviews every model-written answer before it is shown. A clear error gets one repair
    # round; an answer that still fails is not shown. If the reviewer cannot be reached the answer (which already
    # passed every deterministic guard) is shown and the event logged.
    rdpr_verify_answers: bool = True
    rdpr_verify_timeout_seconds: float = 30.0

    # ---- Voice mode (the hands-free voice agent in AI mode; modelled on the Meghalaya voice agent as integrated into
    # KPCL). Same variable names as those apps. Speech to text: qwen3-asr; text to speech: Qwen3-TTS (vLLM-Omni, OpenAI
    # /audio/speech shape) cloning the officer reference clip. Both on the same internal gateway as the SQL model (VPN).
    asr_model: str = "qwen3-asr"
    asr_base_url: str = ""
    asr_api_key: str = ""
    asr_timeout_seconds: float = 60.0
    asr_context_hints_enabled: bool = True        # zilla names and terms as an ASR prompt; an echo of it is dropped
    tts_enabled: bool = False
    tts_model: str = "qwen3-tts"
    tts_base_url: str = ""
    tts_api_key: str = ""
    tts_timeout_seconds: float = 20.0
    tts_voice: str = "serena"
    tts_language: str = "English"
    tts_task_type: str = "CustomVoice"            # Base = clone the reference clip (TTS_REF_AUDIO_PATH)
    # The RDPR persona, sent as the TTS style instruction (Qwen3-TTS honours it for the cloned Base voice too).
    rdpr_voice_instructions: str = (
        "Female voice: a composed, experienced senior officer of Karnataka's Rural Development and Panchayat Raj "
        "Department, about forty, briefing government officials. Medium-low pitch, warm and steady, never shrill or "
        "childlike. Clear, neutral Indian English. Calm, confident, respectful tone. Measured pace, a little slower and "
        "very clear for figures, rupee amounts in lakh and crore, zilla and taluk names and years; a brief pause before "
        "each key figure. Say Karnataka place names the local way.")
    tts_max_new_tokens: int = 2048
    tts_ref_audio_path: str = ""                  # relative paths resolve against ai_app/
    tts_x_vector_only_mode: bool = True
    tts_stream_enabled: bool = True
    tts_stream_sample_rate: int = 24000
    tts_speed_enabled: bool = True
    voice_max_concurrent_calls: int = 4           # ASR/TTS calls in flight at once from this server
    voice_rate_limit_per_minute: int = 240        # transcribe / speak / filler calls per client IP per minute
    voice_max_audio_bytes: int = 10_000_000       # one spoken question as 16 kHz WAV is ~32 KB a second
    voice_max_seconds: float = 30.0               # longest recording accepted as one question
    voice_max_transcript_chars: int = 300         # longest transcript accepted as one question
    voice_collect_mishearings: bool = False       # text only, with the officers' consent: logs/voice_mishearings.jsonl

    @property
    def db_path(self) -> Path:
        return Path(self.rdpr_db_path) if self.rdpr_db_path else DEFAULT_DB_PATH

    @property
    def llm_configured(self) -> bool:
        return bool(self.sql_verify_model and self.sql_verify_base_url and self.sql_verify_api_key)

    @property
    def asr_configured(self) -> bool:
        return bool(self.asr_base_url and self.asr_api_key and self.asr_model)

    @property
    def tts_configured(self) -> bool:
        return bool(self.tts_enabled and self.tts_base_url and self.tts_api_key and self.tts_model)


settings = Settings()
