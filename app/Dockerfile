FROM python:3.12-slim
WORKDIR /app
# Dependencies first, your code last.
# constraints.txt pins the indirect dependencies too (pip freeze of the 5 Nov 2026 image).
COPY app/requirements.txt app/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
# Non-root user.
RUN useradd --uid 1000 --create-home app
COPY sql/queries.sql ./sql/queries.sql
COPY app/*.py ./
COPY app/.streamlit/ ./.streamlit/
# Make the copied files readable by the non-root user, whatever their permissions on the laptop.
RUN chmod -R a+rX /app
USER app
EXPOSE 8501
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1
CMD ["streamlit", "run", "dashboard.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false", "--client.toolbarMode=viewer"]
