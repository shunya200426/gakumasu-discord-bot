# Standard library
import traceback

# Third-party
import discord
from discord.ext import commands

# Local application
from bot.command_loader import register_commands
from bot.interaction_check import create_interaction_access_check
from config.paths import YOLO_MODEL_PATH
from db.database import DatabaseManager
from inference.yolo_detector import YoloDetector
from ocr.tesseract_engine import TesseractEngine
from services.image_consent_service import ImageConsentService
from services.image_storage_service import ImageStorageService
from services.inference_export_service import InferenceExportService
from services.inference_log_recorder import InferenceLogRecorder
from services.inference_service import InferenceService
from services.interaction_access_service import InteractionAccessService
from services.ocr_service import OcrService
from utils.logger import get_logger

log = get_logger()


class GakumasuBot(commands.Bot):
    def __init__(
        self,
        db: DatabaseManager,
        *,
        tessdata_path: str | None,
        dev_user_id: int,
        alert_channel_id: int,
        cooldown_per_guild: int,
        cooldown_per_user: int,
        cooldown_global: int,
    ):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self.db = db

        self.tessdata_path = tessdata_path

        self.dev_user_id = dev_user_id
        self.alert_channel_id = alert_channel_id
        self.cooldown_per_guild = cooldown_per_guild
        self.cooldown_per_user = cooldown_per_user
        self.cooldown_global = cooldown_global

        self.detector: YoloDetector | None = None
        self.tesseract_engine: TesseractEngine | None = None
        self.ocr_service: OcrService | None = None
        self.inference_service: InferenceService | None = None
        self.inference_log_recorder: InferenceLogRecorder | None = None
        self.interaction_access_service: InteractionAccessService | None = None
        self.image_consent_service: ImageConsentService | None = None
        self.image_storage_service: ImageStorageService | None = None
        self.inference_export_service: InferenceExportService | None = None

    async def setup_hook(self) -> None:
        try:
            self._initialize_services()
            self._register_commands()
            self._register_interaction_check()

        except Exception:
            log.error(
                "setup_hook failed:\n%s",
                traceback.format_exc(),
            )
            raise

    def _initialize_services(self) -> None:
        # ====== YOLO ======
        log.info(
            "Initializing YOLO detector..."
        )

        self.detector = YoloDetector(
            model_path=YOLO_MODEL_PATH,
            confidence_threshold=0.25,
            image_size=(640, 640),
            device=None,
        )

        log.info(
            "YOLO detector initialized: "
            "model=%s format=%s classes=%d",
            self.detector.model_name,
            self.detector.model_format,
            len(self.detector.class_names),
        )

        log.info(
            "Running YOLO warmup..."
        )

        self.detector.warmup()

        log.info(
            "YOLO warmup completed."
        )

        # ====== Tesseract ======
        log.info(
            "Initializing Tesseract engine..."
        )

        self.tesseract_engine = TesseractEngine(
            tessdata_path=self.tessdata_path,
        )

        # ====== OCR Service ======
        log.info(
            "Initializing OCR service..."
        )

        self.ocr_service = OcrService(
            engine=self.tesseract_engine,
        )

        log.info(
            "OCR service initialized."
        )

        # ====== Inference Service ======
        log.info(
            "Initializing inference service..."
        )

        self.inference_service = InferenceService(
            detector=self.detector,
            ocr_service=self.ocr_service,
        )

        log.info(
            "Inference service initialized."
        )

        # ====== Inference Log Recorder ======
        log.info(
            "Initializing inference log recorder service..."
        )

        if self.db.inference is None:
            raise RuntimeError(
                "InferenceRepositoryが"
                "初期化されていません。"
            )

        self.inference_log_recorder = (
            InferenceLogRecorder(
                repository=self.db.inference,
                detector=self.detector,
            )
        )

        log.info(
            "Inference log recorder service initialized."
        )

        # ====== Interaction Access Service ======
        log.info(
            "Initializing interaction access service..."
        )

        if (
            self.db.guilds is None
            or self.db.users is None
        ):
            raise RuntimeError(
                "GuildRepositoryまたは"
                "UserRepositoryが"
                "初期化されていません。"
            )

        self.interaction_access_service = (
            InteractionAccessService(
                guild_repository=self.db.guilds,
                user_repository=self.db.users,
            )
        )

        log.info(
            "Interaction access service initialized."
        )

        # ====== Image Consent Service ======
        log.info(
            "Initializing image consent service..."
        )

        self.image_consent_service = (
            ImageConsentService(
                user_repository=self.db.users,
            )
        )

        log.info(
            "Image consent service initialized."
        )

        # ====== Image Storage Service ======
        log.info(
            "Initializing image storage service..."
        )

        self.image_storage_service = (
            ImageStorageService()
        )

        log.info(
            "Image storage service initialized."
        )

        # ====== Inference Export Service ======
        log.info(
            "Initializing inference export service..."
        )

        self.inference_export_service = (
            InferenceExportService()
        )

        log.info(
            "Inference export service initialized."
        )

    def _register_commands(self) -> None:
        register_commands(self)

    def _register_interaction_check(self) -> None:
        self.tree.interaction_check = (
            create_interaction_access_check(
                dev_user_id=self.dev_user_id,
                alert_channel_id=self.alert_channel_id,
                cooldown_per_guild=self.cooldown_per_guild,
                cooldown_per_user=self.cooldown_per_user,
                cooldown_global=self.cooldown_global,
            )
        )

        log.info(
            "Assigned global interaction access check "
            "to command tree"
        )