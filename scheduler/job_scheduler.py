"""
Job scheduler for automatic tender updates every 6 hours.
Requirement: "The inspection and update process must take place every 6 hours at most."
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from datetime import datetime
from typing import Dict, Any, Callable
from loguru import logger
import sys


class TenderScheduler:
    """Manages scheduled tender scraping jobs"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize scheduler
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.update_interval = config.get('scraper', {}).get('update_interval_hours', 6)
        
        # Initialize APScheduler
        self.scheduler = BackgroundScheduler(
            timezone='Europe/Rome',  # Italian timezone
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1,  # Don't run concurrent jobs
                'misfire_grace_time': 300  # 5 minutes grace period
            }
        )
        
        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        logger.info(f"Scheduler initialized: {self.update_interval}h interval")
    
    def add_scraper_job(self, scraper_func: Callable, platform_name: str):
        """
        Add a scraper job to the scheduler
        
        Args:
            scraper_func: Function to call for scraping
            platform_name: Name of the platform
        """
        job_id = f"scraper_{platform_name}"
        
        # Add job with interval trigger
        self.scheduler.add_job(
            func=scraper_func,
            trigger=IntervalTrigger(hours=self.update_interval),
            id=job_id,
            name=f"{platform_name} Scraper",
            replace_existing=True,
            next_run_time=datetime.now()  # Run immediately on start
        )
        
        logger.info(f"Added job: {job_id} (every {self.update_interval}h)")
    
    def add_level2_job(self, processor_func: Callable):
        """
        Add Level 2 data extraction job
        
        Args:
            processor_func: Function to call for Level 2 processing
        """
        # Run Level 2 processing less frequently (every 12 hours)
        self.scheduler.add_job(
            func=processor_func,
            trigger=IntervalTrigger(hours=self.update_interval * 2),
            id="level2_processor",
            name="Level 2 Data Extractor",
            replace_existing=True,
            next_run_time=datetime.now()
        )
        
        logger.info("Added Level 2 processing job")
    
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
            self._print_jobs()
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    
    def pause(self):
        """Pause all jobs"""
        self.scheduler.pause()
        logger.info("Scheduler paused")
    
    def resume(self):
        """Resume all jobs"""
        self.scheduler.resume()
        logger.info("Scheduler resumed")
    
    def run_job_now(self, job_id: str):
        """
        Trigger a job to run immediately
        
        Args:
            job_id: Job identifier
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"Triggered job: {job_id}")
                return True
            else:
                logger.warning(f"Job not found: {job_id}")
                return False
        except Exception as e:
            logger.error(f"Error triggering job {job_id}: {e}")
            return False
    
    def get_jobs(self) -> list:
        """Get list of all scheduled jobs"""
        return self.scheduler.get_jobs()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get status of a specific job
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status dictionary
        """
        job = self.scheduler.get_job(job_id)
        
        if not job:
            return {'exists': False}
        
        return {
            'exists': True,
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time,
            'trigger': str(job.trigger)
        }
    
    def _print_jobs(self):
        """Print all scheduled jobs"""
        jobs = self.get_jobs()
        
        if not jobs:
            logger.info("No jobs scheduled")
            return
        
        logger.info(f"Scheduled jobs ({len(jobs)}):")
        for job in jobs:
            logger.info(f"  - {job.name} (ID: {job.id})")
            logger.info(f"    Next run: {job.next_run_time}")
            logger.info(f"    Trigger: {job.trigger}")
    
    def _job_executed(self, event):
        """Handler for successful job execution"""
        job = self.scheduler.get_job(event.job_id)
        if job:
            logger.info(f"Job executed: {job.name} (ID: {event.job_id})")
            logger.info(f"  Next run: {job.next_run_time}")
    
    def _job_error(self, event):
        """Handler for job execution errors"""
        job = self.scheduler.get_job(event.job_id)
        job_name = job.name if job else event.job_id
        
        logger.error(f"Job failed: {job_name}")
        logger.error(f"  Exception: {event.exception}")
        logger.error(f"  Traceback: {event.traceback}")
    
    def keep_alive(self):
        """
        Keep the scheduler running (blocking)
        Use this in the main thread to prevent program exit
        """
        logger.info("Scheduler running. Press Ctrl+C to exit.")
        
        try:
            # Keep main thread alive
            while True:
                import time
                time.sleep(60)
                
                # Log status every hour
                if datetime.now().minute == 0:
                    self._print_jobs()
        
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown signal received")
            self.stop()
            sys.exit(0)


if __name__ == '__main__':
    # Test scheduler
    import yaml
    from loguru import logger
    
    # Configure logger
    logger.add("logs/scheduler.log", rotation="1 day")
    
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    scheduler = TenderScheduler(config)
    
    # Add a test job
    def test_job():
        logger.info("Test job executed!")
    
    scheduler.add_scraper_job(test_job, "test")
    scheduler.start()
    
    print("Scheduler started. Press Ctrl+C to exit.")
    scheduler.keep_alive()
