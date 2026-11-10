import { defineConfig } from "vitest/config";

// 순수 로직(입력 검증, API 클라이언트) 단위 테스트용 — DOM이 필요 없어 node 환경으로 실행한다
export default defineConfig({
  resolve: { tsconfigPaths: true }, // "@/..." 경로 별칭
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
