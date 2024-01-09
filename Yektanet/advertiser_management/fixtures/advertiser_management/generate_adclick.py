import json
import random
from datetime import datetime, timedelta

click_chance = 0.4

adview_path = "adview.json"
adclick_path = "adclick.json"

with open(adview_path, "r") as f:
    adview = json.load(f)


data = []
for view in adview:
    if random.random() > click_chance:
        continue

    view_date = view["fields"]["created_at"]
    new_date = datetime.strptime(view_date, "%Y-%m-%d %H:%M:%S")

    # click date should be after view date (between 1 second to 5 minutes)
    new_date += timedelta(
        minutes=random.randint(0, 5),
        seconds=random.randint(1, 60),
    )
    new_date = new_date.strftime("%Y-%m-%d %H:%M:%S")

    click = {
        "model": "advertiser_management.adclick",
        "pk": len(data) + 1,
        "fields": {
            "ad": view["fields"]["ad"],
            "ip": view["fields"]["ip"],
            "created_at": new_date,
        },
    }

    data.append(click)

print(f"Generated {len(data)} clicks")

# save data
with open(adclick_path, "w") as f:
    json.dump(data, f, indent=4)
