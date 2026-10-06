# AutoDFBench evaluation APIs in one container. Ground truth: ground_truth/autodfbench_gt.sqlite (in the repo).
# Python 3.12: the file-carving API uses the cgi module, removed in 3.13.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AUTODFBENCH_RESULTS_DB=/app/results/autodfbench_results.sqlite \
    MAIN_PATH=/app

WORKDIR /app

COPY requirements-api.txt /tmp/requirements-api.txt
RUN pip install -r /tmp/requirements-api.txt

COPY . /app

EXPOSE 8000 8001 8002 8003 8004

CMD ["python", "serve.py"]
