FROM python:3.12-slim

WORKDIR /app

# Copy only what we need for installation/runtime
COPY packages/math-sdk ./packages/math-sdk
COPY packages/stake-math-service ./packages/stake-math-service

RUN pip install --no-cache-dir -r packages/stake-math-service/requirements.txt \
  && pip install --no-cache-dir -e packages/math-sdk \
  && pip install --no-cache-dir -e packages/stake-math-service

ENV STAKE_MATH_WORKSPACES_DIR=/data/workspaces
VOLUME ["/data/workspaces"]

EXPOSE 8787
CMD ["sh", "-c", "uvicorn stake_math_service.main:app --host 0.0.0.0 --port ${PORT:-8787}"]


