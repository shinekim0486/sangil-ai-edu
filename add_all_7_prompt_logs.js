const fs = require('fs');

const p = '05-학생산출물/index.html';
let html = fs.readFileSync(p, 'utf8');

const oldPillar = `          {
            title: "📊 7개 교과 프롬프트 로그 (3,383건)",
            badge: "엑셀 로그",
            items: [
              { name: "3D프린터용제품제작 프롬프트 로그", desc: "학생 대화 엑셀 원장 (149KB)", url: "프롬포트로그/3D프린터용제품제작_프롬포트로그.xlsx", type: "data" },
              { name: "게임프로그래밍 프롬프트 로그", desc: "학생 대화 엑셀 원장 (100KB)", url: "프롬포트로그/게임프로그래밍_프롬포트로그.xlsx", type: "data" },
              { name: "네트워크프로그래밍 프롬프트 로그", desc: "학생 대화 엑셀 원장 (151KB)", url: "프롬포트로그/네트워크프로그래밍_프롬포트로그.xlsx", type: "data" },
              { name: "인공지능모델링 프롬프트 로그", desc: "학생 대화 엑셀 원장 (96KB)", url: "프롬포트로그/인공지능모델링_프롬포트로그.xlsx", type: "data" }
            ]
          }`;

const newPillar = `          {
            title: "📊 7개 전문교과 프롬프트 로그 전수 (3,383건)",
            badge: "엑셀 로그 7종 완비",
            items: [
              { name: "01. 응용프로그래밍개발 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (53KB)", url: "프롬포트로그/응용프로그래밍개발_프롬포트로그.xlsx", type: "data" },
              { name: "02. 3D프린터용제품제작 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (149KB)", url: "프롬포트로그/3D프린터용제품제작_프롬포트로그.xlsx", type: "data" },
              { name: "03. 게임프로그래밍 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (101KB)", url: "프롬포트로그/게임프로그래밍_프롬포트로그.xlsx", type: "data" },
              { name: "04. 네트워크프로그래밍 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (152KB)", url: "프롬포트로그/네트워크프로그래밍_프롬포트로그.xlsx", type: "data" },
              { name: "05. 인공지능모델링 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (97KB)", url: "프롬포트로그/인공지능모델링_프롬포트로그.xlsx", type: "data" },
              { name: "06. 시스템운영및네트워크운영 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (89KB)", url: "프롬포트로그/시스템운영및네트워크운영_프롬포트로그.xlsx", type: "data" },
              { name: "07. 스마트문화앱콘텐츠제작 프롬프트 로그", desc: "학생 챗봇 대화 엑셀 원장 (64KB)", url: "프롬포트로그/스마트문화앱콘텐츠제작_프롬포트로그.xlsx", type: "data" }
            ]
          }`;

if (html.includes(oldPillar)) {
  html = html.replace(oldPillar, newPillar);
  fs.writeFileSync(p, html, 'utf8');
  console.log('Successfully updated all 7 prompt logs in 05-학생산출물/index.html!');
} else {
  console.log('Old pillar string not found!');
}
