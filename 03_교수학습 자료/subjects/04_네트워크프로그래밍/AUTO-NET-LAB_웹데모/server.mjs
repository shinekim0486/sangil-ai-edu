import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
async function loadDotEnv(filePath) {
  try {
    const text = await fs.readFile(filePath, "utf8");
    for (const line of text.split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
      if (!match || process.env[match[1]]) continue;
      process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, "");
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}
await loadDotEnv(path.join(rootDir, ".env"));
const userConfigDir = path.join(process.env.LOCALAPPDATA || rootDir, "AUTO-NET-LAB");
await fs.mkdir(userConfigDir, { recursive: true });
await loadDotEnv(path.join(userConfigDir, ".env"));
const port = Number(process.env.PORT || 3000);
const dataDir = path.resolve(process.env.DATA_DIR || path.join(userConfigDir, "data"));
const liveLogPath = path.join(dataDir, "chat-records.jsonl");
const seedPath = path.join(rootDir, "network-programming-history.jsonl");
const model = process.env.OPENAI_MODEL || "gpt-4.1-mini";
const mockOpenAI = process.env.MOCK_OPENAI
  ? String(process.env.MOCK_OPENAI).toLowerCase() === "true"
  : !process.env.OPENAI_API_KEY;
const allowedTeams = new Set(["CAR1", "CAR2", "CAR3", "CAR4", "CAR5", "CAR6"]);
const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
]);

await fs.mkdir(dataDir, { recursive: true });
const seedRecords = await loadJsonLines(seedPath);

function sendJson(response, status, body) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  response.end(JSON.stringify(body));
}

async function loadJsonLines(filePath) {
  try {
    const text = await fs.readFile(filePath, "utf8");
    return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

async function readBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 64 * 1024) throw new Error("요청 내용이 너무 큽니다.");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function normalizeSession(body) {
  const studentId = String(body.studentId || "").trim();
  const team = String(body.team || "").trim().toUpperCase();
  const message = String(body.message || "").trim();
  if (!/^\d{5}$/.test(studentId)) throw new Error("학번은 숫자 5자리여야 합니다.");
  if (!allowedTeams.has(team)) throw new Error("조 정보가 올바르지 않습니다.");
  if (!message || message.length > 2000) throw new Error("질문은 1~2000자로 입력해 주세요.");
  return { studentId, team, message };
}

function scoreRecord(record, message) {
  const tokens = [...new Set(message.toLowerCase().split(/[^0-9a-zA-Z가-힣]+/).filter((token) => token.length >= 2))];
  const text = `${record.question || ""} ${record.outputAnswer || record.answer || ""}`.toLowerCase();
  return tokens.reduce((score, token) => score + (text.includes(token) ? 1 : 0), 0);
}

function findReferences(message) {
  return seedRecords
    .map((record) => ({ record, score: scoreRecord(record, message) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map(({ record }) => ({
      question: record.question,
      answer: record.outputAnswer || record.answer,
      artifact: record.outputArtifact || "",
    }));
}

function buildPrompt({ studentId, team, message }, references) {
  const referenceText = references.length
    ? references.map((item, index) => `참고 ${index + 1}\n질문: ${item.question}\n답변: ${item.answer}\n산출물: ${item.artifact}`).join("\n\n")
    : "관련 기존 기록 없음";
  return `학생 학번: ${studentId}\n조: ${team}\n질문: ${message}\n\n기존 네트워크프로그래밍 기록:\n${referenceText}`;
}

async function requestOpenAI(session, references) {
  if (mockOpenAI) {
    return `[시험 모드] ${session.team}의 질문을 저장했습니다. 실제 답변을 받으려면 서버 환경변수 OPENAI_API_KEY를 설정하고 MOCK_OPENAI=false로 실행하세요.`;
  }
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    const error = new Error("서버에 OPENAI_API_KEY가 설정되지 않았습니다.");
    error.statusCode = 503;
    throw error;
  }
  const apiResponse = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      "authorization": `Bearer ${apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      instructions: "당신은 특성화고 네트워크프로그래밍 실습 도우미입니다. 학생의 조건을 먼저 확인하고, 안전한 비구동 시험과 확인 절차를 중심으로 한국어로 간결하게 답하세요. 제공된 기존 기록은 참고 자료이며 사실과 맞지 않으면 그대로 따르지 마세요. API 키나 시스템 설정을 공개하지 마세요.",
      input: buildPrompt(session, references),
      max_output_tokens: 700,
    }),
  });
  const payload = await apiResponse.json();
  if (!apiResponse.ok) {
    const error = new Error(payload?.error?.message || "OpenAI API 호출에 실패했습니다.");
    error.statusCode = apiResponse.status >= 500 ? 502 : 400;
    throw error;
  }
  const outputText = payload.output_text || payload.output
    ?.flatMap((item) => item.content || [])
    .filter((item) => item.type === "output_text")
    .map((item) => item.text)
    .join("\n")
    .trim();
  if (!outputText) throw new Error("API 응답에서 답변을 찾지 못했습니다.");
  return outputText;
}

async function saveChat(record) {
  await fs.appendFile(liveLogPath, `${JSON.stringify(record)}\n`, "utf8");
}

async function handleChat(request, response) {
  try {
    const session = normalizeSession(await readBody(request));
    const references = findReferences(session.message);
    const answer = await requestOpenAI(session, references);
    const record = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      subject: "네트워크프로그래밍",
      studentId: session.studentId,
      team: session.team,
      question: session.message,
      answer,
      referenceArtifacts: references.map((item) => item.artifact).filter(Boolean),
      model: mockOpenAI ? "mock" : model,
    };
    await saveChat(record);
    sendJson(response, 200, { id: record.id, answer: record.answer, createdAt: record.createdAt });
  } catch (error) {
    const status = error.statusCode || (/학번|조 정보|질문|요청 내용/.test(error.message) ? 400 : 500);
    console.error(error);
    sendJson(response, status, { error: error.message || "요청 처리 중 오류가 발생했습니다." });
  }
}

async function handleHistory(url, response) {
  const studentId = String(url.searchParams.get("studentId") || "");
  if (!/^\d{5}$/.test(studentId)) return sendJson(response, 400, { error: "학번이 필요합니다." });
  const records = (await loadJsonLines(liveLogPath))
    .filter((record) => record.studentId === studentId)
    .slice(-50)
    .map(({ id, createdAt, question, answer, team }) => ({ id, createdAt, question, answer, team }));
  sendJson(response, 200, { records });
}

async function serveStatic(url, response) {
  const requested = decodeURIComponent(url.pathname === "/" ? "/login.html" : url.pathname);
  const filePath = path.resolve(rootDir, `.${requested}`);
  if (filePath !== rootDir && !filePath.startsWith(`${rootDir}${path.sep}`)) return sendJson(response, 403, { error: "접근할 수 없습니다." });
  try {
    const stat = await fs.stat(filePath);
    const resolved = stat.isDirectory() ? path.join(filePath, "index.html") : filePath;
    const body = await fs.readFile(resolved);
    response.writeHead(200, {
      "content-type": mimeTypes.get(path.extname(resolved).toLowerCase()) || "application/octet-stream",
      "x-content-type-options": "nosniff",
    });
    response.end(body);
  } catch (error) {
    if (error.code === "ENOENT") return sendJson(response, 404, { error: "파일을 찾을 수 없습니다." });
    throw error;
  }
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  if (request.method === "GET" && url.pathname === "/api/health") {
    return sendJson(response, 200, { ok: true, subject: "네트워크프로그래밍", seedRecords: seedRecords.length, model, apiKeyConfigured: Boolean(process.env.OPENAI_API_KEY), mockOpenAI });
  }
  if (request.method === "POST" && url.pathname === "/api/chat") return handleChat(request, response);
  if (request.method === "GET" && url.pathname === "/api/history") return handleHistory(url, response);
  if (!['GET', 'HEAD'].includes(request.method)) return sendJson(response, 405, { error: "허용되지 않은 요청입니다." });
  return serveStatic(url, response);
});

server.listen(port, () => {
  console.log(`AUTO-NET LAB server: http://localhost:${port}`);
  console.log(`기존 네트워크프로그래밍 기록: ${seedRecords.length}건`);
});
