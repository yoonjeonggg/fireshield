import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAdminStats, fetchPublicStats, verifyRequest } from "@/lib/api";

const payload = {
  claimed_org: "서울소방서",
  claimed_person: "김소방",
  claim_type: "law_amendment",
  target_business: "한국소방설비",
};

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(typeof body === "string" ? body : JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("verifyRequest", () => {
  it("성공 응답을 그대로 돌려주고 JSON으로 POST한다", async () => {
    const fetchMock = mockFetch(200, { risk_level: "safe", score: 10 });

    await expect(verifyRequest(payload)).resolves.toEqual({ risk_level: "safe", score: 10 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/verify$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it("서버가 준 detail 메시지를 오류로 보여준다 (422 입력 거부)", async () => {
    mockFetch(422, { error: "invalid_request", detail: "의미 없는 입력입니다." });
    await expect(verifyRequest(payload)).rejects.toThrow("의미 없는 입력입니다.");
  });

  it("요청 횟수 제한(429) 메시지를 그대로 보여준다", async () => {
    mockFetch(429, { detail: "요청이 너무 많습니다. 42초 후 다시 시도해주세요." });
    await expect(verifyRequest(payload)).rejects.toThrow("42초 후 다시 시도");
  });

  it("오류 본문이 JSON이 아니면 기본 메시지를 쓴다", async () => {
    mockFetch(502, "<html>Bad Gateway</html>");
    await expect(verifyRequest(payload)).rejects.toThrow("요청 처리 중 오류가 발생했습니다.");
  });
});

describe("조회 API", () => {
  it("실패하면 화면용 오류 메시지를 던진다", async () => {
    mockFetch(500, {});
    await expect(fetchPublicStats()).rejects.toThrow("통계 데이터를 불러오지 못했습니다.");
  });

  it("관리자 키가 틀리면(403) 인증 실패 메시지를 던지고 키를 헤더로 보낸다", async () => {
    const fetchMock = mockFetch(403, {});
    await expect(fetchAdminStats("wrong-key")).rejects.toThrow("관리자 인증에 실패했습니다");
    expect(fetchMock.mock.calls[0][1].headers).toEqual({ "X-Admin-Key": "wrong-key" });
  });
});
