FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .

# Port 8000 is used by the web dashboard (web/app.py with uvicorn).
# To run the web dashboard: docker run -p 8000:8000 <image> python -m uvicorn web.app:app --host 0.0.0.0 --port 8000
EXPOSE 8000

# Default command runs the CLI kernel. Override with the uvicorn command above
# to start the web dashboard instead.
CMD ["python", "runner.py"]
