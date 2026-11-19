FROM python:3.12-slim
WORKDIR /app
# Dependencies first, our code last.
# constraints.txt pins the indirect dependencies too (pip freeze of the built image).
COPY loader/requirements.txt loader/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
# Non-root user. It writes the downloaded files in /data (./data on the laptop).
RUN useradd --uid 1000 --create-home loader
COPY sql/ ./sql/
COPY loader/load_fda.py ./
# Make the copied files readable by the non-root user, whatever their permissions on the laptop.
RUN chmod -R a+rX /app
USER loader
CMD ["python", "load_fda.py"]
