import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import subprocess
from typing import List, Set

def run_unit_tests():
    for test_cmd in [["py", "-3.13", "-m", "pytest"], ["pytest"], [sys.executable, "-m", "pytest"]]:
        try:
            res = subprocess.run(test_cmd, capture_output=True, text=True, encoding='utf-8')
            if res.returncode == 0:
                return 0, res.stdout
            elif "No module named pytest" not in (res.stderr or "") and "not recognized" not in (res.stderr or ""):
                return res.returncode, (res.stderr or res.stdout)
        except Exception:
            continue
    return 1, "pytest 실행 환경을 찾지 못했습니다."

def run_cmd(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        return res.stdout.strip()
    except Exception:
        return ''

def main() -> int:
    # 1. Check changed files between origin/main and HEAD
    diff_output = run_cmd(['git', 'diff', '--name-only', 'origin/main..HEAD'])
    if not diff_output:
        diff_output = run_cmd(['git', 'diff', '--name-only', 'HEAD~1..HEAD'])

    changed_files: Set[str] = set(diff_output.splitlines()) if diff_output else set()

    # Check if core code files changed
    code_changed = any(
        f == 'briefing_auto.py' or f.startswith('tests/')
        for f in changed_files
    )

    if not code_changed:
        # No code files modified, allow push
        return 0

    # Required 5 governance documents (SOP 3)
    required_docs = {
        'README.md',
        'update.md',
        '03.Committee_Opinions.md',
        '04.Data_Collection_Log.md',
        'LOGLIST.md'
    }

    missing_docs = required_docs - changed_files
    if missing_docs:
        print('\n' + '=' * 76)
        print('🚨 [거버넌스 경고 (SOP 3 위반)] 5대 필수 연구 자산 문서 동기화 누락!')
        print('-' * 76)
        print('코드 파일(briefing_auto.py, tests/ 등)이 수정되었으나,')
        print('SOP 3에 규정된 5대 필수 문서 중 다음 문서가 이번 커밋에 누락되었습니다:')
        for doc in sorted(missing_docs):
            print(f'  ❌ {doc}')
        print('\n[해결 방법]')
        print('  1. python sync_release.py --version [버전] --desc "[내용]" --push 실행')
        print('  2. 또는 누락된 문서를 함께 수동 수정 후 커밋하여 푸시하십시오.')
        print('=' * 76 + '\n')
        return 1

    # 2. Run unit tests to ensure no broken code is pushed
    print('[Pre-Push] 15개 단위 테스트 무결성 전수 검증 중...')
    ret_code, test_output = run_unit_tests()
    if ret_code != 0:
        print('\n' + '=' * 76)
        print('🚨 [Pre-Push 차단] 단위 테스트 실패! 모든 테스트가 통과해야 푸시 가능합니다.')
        print('-' * 76)
        print(test_output[-400:])
        print('=' * 76 + '\n')
        return 1

    print('✅ [Pre-Push 통과] 5대 거버넌스 문서 동기화 및 15개 단위 테스트 전수 통과 확인.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
