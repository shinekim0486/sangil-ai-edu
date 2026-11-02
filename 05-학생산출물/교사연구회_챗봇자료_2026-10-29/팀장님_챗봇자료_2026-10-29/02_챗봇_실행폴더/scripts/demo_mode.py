"""비용 없는 화면 체험. 실제 키가 있어도 API 클라이언트를 만들지 않는다."""
from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DATA_DIR']=str(ROOT/'demo_data')
import db
import llm
llm.MOCK=True
llm._client=None
def disabled_init():
    llm.MOCK=True
    llm._client=None
    return False
llm.init=disabled_init
import app as web
web.TEAM_CODES=['DEMO']
web.ACCESS_CODE=''
web.ADMIN_KEY=''
if __name__=='__main__':
    print('화면 체험 모드 API 호출 없음 / 팀 코드 DEMO',flush=True)
    print('브라우저에서 http://127.0.0.1:5001 을 여세요.',flush=True)
    web.app.run(host='127.0.0.1',port=5001,debug=False)
