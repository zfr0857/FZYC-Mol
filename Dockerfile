FROM python:3.13.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /audit

COPY requirements-lock.txt /tmp/requirements-lock.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements-lock.txt

COPY . /audit

CMD ["python", "scripts/reproduce_analysis.py", "--config", "configs/paper.yaml"]
