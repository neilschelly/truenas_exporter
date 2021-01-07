IMAGE   ?= truenas_exporter:latest
NAME    ?= ird-truenas-exporter

attach:
	docker exec -it $(NAME) /bin/bash

build:
	docker build -t $(IMAGE) .

stop:
	docker stop $(NAME)

start:
	docker start $(NAME)

run:
	docker run -d \
	  --log-opt max-size=100M \
	  --name $(NAME) \
	  -p 9912:9912 \
	  $(IMAGE)

destroy:
	docker rm $(NAME)
	
restart: destroy run

logs:
	docker logs -f $(NAME)

FORCE:
