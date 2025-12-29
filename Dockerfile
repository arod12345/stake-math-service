FROM python:3.12-slim

# Needed for `pip install git+...`
RUN apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app/service

# Build context should be `packages/stake-math-service/` on Render
COPY . .

# Install service deps + math-sdk from upstream Git (avoids needing monorepo context)
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir "git+https://github.com/StakeEngine/math-sdk.git@0842bb244cb8c15e63af541054710a8082901e2f#egg=stakeengine" \
  && pip install --no-cache-dir -e .

ENV STAKE_MATH_WORKSPACES_DIR=/data/workspaces
VOLUME ["/data/workspaces"]

EXPOSE 8787
CMD ["sh", "-c", "uvicorn stake_math_service.main:app --host 0.0.0.0 --port ${PORT:-8787}"]


