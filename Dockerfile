FROM python:3.11-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is bind-mounted over this in dev (see docker-compose.yml) so edits
# outside the container are picked up without a rebuild. This COPY keeps the
# image runnable standalone (e.g. in CI) when nothing is mounted.
COPY . .

CMD ["python", "check_tools.py"]
