import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

import config

jobs_bp = Blueprint('jobs', __name__)
JOBS_FILE = os.path.join(config.ROOT_HERMES_FOLDER, "cron/jobs.json")


def load_jobs():
    try:
        with open(JOBS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"jobs": []}


@jobs_bp.route("/")
@login_required
def index():
    data = load_jobs()
    return render_template('jobs.html', jobs=data.get("jobs", []), updated_at=data.get("updated_at", "Unknown"), active_page='jobs')
