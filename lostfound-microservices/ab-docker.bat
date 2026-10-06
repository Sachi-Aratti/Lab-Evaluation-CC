@echo off
docker run --rm --network lostfound-microservices_lostfound-network httpd:2.4 ab %*
