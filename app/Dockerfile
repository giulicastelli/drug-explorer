FROM python:3.12-slim
WORKDIR /app
# Dependencies first, our code last: a code change does not reinstall the libraries.
# constraints.txt pins the indirect dependencies too (pip freeze of the built image).
COPY app/requirements.txt app/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
# Non-root user.
RUN useradd --uid 1000 --create-home app
COPY sql/queries.sql ./sql/queries.sql
COPY app/server.py ./
COPY app/static ./static
# Make the copied files readable by the non-root user, whatever their permissions on the laptop.
RUN chmod -R a+rX /app
USER app
EXPOSE 8080
# Docker marks the container healthy when the page answers.
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
