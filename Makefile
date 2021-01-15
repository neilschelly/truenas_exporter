NAME    ?= truenas_exporter
TARGET  ?= truenas.example.net

attach:
	docker exec -it $(NAME) /bin/bash

build:
	docker build -t $(NAME):latest .

stop:
	docker stop $(NAME)

start:
	docker start $(NAME)

run:
	docker run -d \
	  --log-opt max-size=100M \
	  --name $(NAME) \
	  -e TRUENAS_USER \
	  -e TRUENAS_PASS \
	  -p 9912:9912 \
	  $(NAME):latest --target $(TARGET)

destroy:
	docker rm $(NAME)
	
restart: destroy run

logs:
	docker logs -f $(NAME)

FORCE:
