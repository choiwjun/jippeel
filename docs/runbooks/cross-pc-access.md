# 다른 PC에서 작품 확인하기

Jippeel은 하나의 SQLite DB를 사용하는 웹앱이다. 다른 PC에서 같은 작품을
확인하려면 작품을 복사하지 않고, 작품 DB가 있는 A PC를 서버로 실행한 뒤
B PC가 같은 웹앱 주소에 접속한다.

## 사용 방법

1. A PC에서 `Jippeel실행.bat`을 실행한다.
2. 실행 창에 표시된 `[B PC]` 주소를 확인한다. 예: `http://192.168.0.12:8000`
3. B PC를 A PC와 같은 Wi-Fi/유선 네트워크에 연결한다.
4. B PC의 브라우저에서 표시된 주소를 연다.

A PC의 앱이 실행 중이고 A PC가 켜져 있는 동안에는 두 PC가 같은 작품 데이터를
본다. 자동저장된 변경은 같은 DB에 기록되므로 별도 가져오기/내보내기가 필요
없다.

## 연결되지 않을 때

Windows 방화벽이 막으면 A PC에서 관리자 PowerShell로 사설 네트워크에 한해
TCP 8000을 허용한다.

```powershell
New-NetFirewallRule -DisplayName "Jippeel LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Profile Private -Action Allow
```

그래도 연결되지 않으면 두 PC가 같은 네트워크인지, A PC의 주소가 바뀌지 않았는지,
Jippeel 실행 창에 오류가 없는지 확인한다.

## 범위와 보안

- 현재 방식은 같은 LAN에서의 열람/집필 공유다. A PC가 꺼져 있으면 B PC에서
  접근할 수 없다.
- 로그인 기능이 없는 현재 앱을 인터넷에 직접 공개하거나 공유기 포트포워딩하지
  않는다. 인터넷 어디서나, A PC가 꺼져 있어도 보려면 인증을 포함한 별도
  클라우드 서버 배포가 필요하다.
- 두 PC가 동시에 편집하면 마지막 저장이 반영된다. 이번 범위는 실시간 공동편집이나
  충돌 해결이 아니라 동일 서버의 작품 확인이다.
