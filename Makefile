# Simplest way to build and push:
# make push

# Replace your_username with your actual Docker Hub username
USERNAME=your_username

push:
	docker build -t $(USERNAME)/ah-dawn-al .
	docker push $(USERNAME)/ah-dawn-al
