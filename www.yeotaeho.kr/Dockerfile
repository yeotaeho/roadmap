FROM node:20-alpine

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# package.json과 pnpm-lock.yaml 복사
COPY package.json pnpm-lock.yaml ./

# 의존성 설치
RUN pnpm install --frozen-lockfile

# 소스 코드 복사
COPY . .

# Next.js 빌드
RUN pnpm run build

# 포트 노출
EXPOSE 3000

# 프로덕션 서버 시작
CMD ["pnpm", "start"]

