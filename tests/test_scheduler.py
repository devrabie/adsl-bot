import pytest
from unittest.mock import AsyncMock, MagicMock
from services.scheduler import setup_scheduler, run_periodic_check_job
from core.models import Line

@pytest.mark.asyncio
async def test_setup_scheduler():
    bot = MagicMock()
    scheduler = setup_scheduler(bot)
    assert scheduler is not None
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "daily_dsl_report_job" in job_ids
    assert "periodic_dsl_check_job" in job_ids
