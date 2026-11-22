# LAN 현황판 서비스 추가 패치 (적용하지 않음)

아래 블록만 저장소 최상위 docker-compose.trading.yml의 services 아래에 추가한다. 기존 서비스는 변경하지 않는다.

~~~yaml
  research-dashboard:
    image: nginx:1.27-alpine
    profiles: ["dashboard"]
    ports:
      - "192.168.0.12:8765:80"
    volumes:
      - ./trading/research_dashboard/dist:/usr/share/nginx/html:ro
      - ./trading/research_dashboard/deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks: [trading]
    restart: unless-stopped
~~~

호스트 주소에만 바인딩한다. 0.0.0.0 바인딩, 터널, 공개 주소는 포함하지 않는다. nginx.conf는 GET 외 요청을 거부하고 data.json에는 Cache-Control: no-store를 설정한다. 이 문서는 제안 패치이며 compose 원본에는 적용하지 않았다.
