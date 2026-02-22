from fastapi import APIRouter

from app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/home")


@router.get("/")
def home():
    logger.info("home page accessed")
    logger.debug("home page accessed")
    logger.error("home page accessed")
    logger.warning("home page accessed")
    logger.critical("home page accessed")
    return {"message": "Welcome to the NextGen Bank API"}