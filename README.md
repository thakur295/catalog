# Item Catalog

##Introduction
It is an application that provides a list of items within a 
variety of categories as well as provide a user registration and 
authentication system with Google+ and facebook. Registered users will have the ability to post, 
edit and delete their own items.

##Procedures to run the Application

## Set up Google Plus auth application.
1.Go to https://console.developers.google.com/project and login.
2.Create a new project
3.Name the project
4.Select "API's and Auth-> Credentials-> Create a new OAuth client ID" from the project menu
5.click Web Application
6.Type the product name and save.
7.In Authorized javascript origins add: http://localhost:5000
8.Click create client ID
9.Click download JSON and save it into the root directory of this project.
10.Rename the JSON file "client_secret.json"

## Set Up facebook auth application:
1. go to https://developers.facebook.com/ and login with Facebook.
2. In the drop down menu at far right click on add new application.
3. Make your own fb_client_secrets.json file.
4. add manually client_id and secret to it
5. click on add product and add Facebook Login and add http://localhost:5000 in javascript origins.
## Database setup
1.Open terminal in the root directory and use the command `vagrant up`
2.After successfully setting up vagrant then write `vagarnt ssh` in you terminal
3. Goto your project root directory and write `python project.py` in your terminal
4. This will start your server on your machine

##Run the application
1. open browser on your machine
2. Type http://localhost:5000 in your browser
