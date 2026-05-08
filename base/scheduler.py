import time
from django.utils import timezone
from django.core.cache import cache
from base.services.data_export_cron import export_and_email_data


def seconds_until_next_hour():
    now = timezone.localtime()
    return (
        (60 - now.minute) * 60
        - now.second
    )


def run_scheduler():
    print("🚀 Scheduler started (exact hour mode)...")

    # Wait until next exact hour FIRST
    sleep_time = seconds_until_next_hour()
    print(f"Waiting {sleep_time} seconds until next full hour...")
    time.sleep(sleep_time)

    while True:
        now = timezone.localtime()
        hour = now.hour

        key = f"export_sent_{now.strftime('%Y%m%d%H')}"

        if 7 <= hour < 19 and not cache.get(key):
            print(f"✅ Running export at {now}")

            export_and_email_data()

            # lock for this hour
            cache.set(key, True, timeout=3600)

        else:
            print(f"⏳ Skipped at {now}")

        # 🔁 Now always sleep exactly 1 hour
        time.sleep(3600)