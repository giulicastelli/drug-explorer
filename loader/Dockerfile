FROM python:3.12-slim
WORKDIR /app
# Dependencies first, your code last: the pip layer is reused when only the code changes.
# constraints.txt pins the indirect dependencies too (pip freeze of the 5 Nov 2026 image).
COPY loader/requirements.txt loader/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
# Non-root user. UID 1000 owns ./data on most laptops.
RUN useradd --uid 1000 --create-home loader
COPY sql/ ./sql/
COPY loader/*.py ./
# Make the copied files readable by the non-root user, whatever their permissions on the laptop.
RUN chmod -R a+rX /app
USER loader
CMD ["python", "load_fda.py"]
