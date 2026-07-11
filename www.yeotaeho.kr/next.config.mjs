/** @type {import('next').NextConfig} */
const nextConfig = {
  // 도커 배포용 — 런타임에 필요한 파일만 모은 standalone 서버(server.js)를 생성한다.
  output: 'standalone',
};

export default nextConfig;
