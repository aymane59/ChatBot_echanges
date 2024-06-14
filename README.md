# ChatBot_echanges

Cette couche de l'application gère la communication entre le le middleware qui est une application Flask (app.py) et les client via socketio de python. Cette communication est sécurisée et chiffrée via SSL.
D'une autre part, le fichier rabbitMQ_handler gère le comportement des deux files d'attente INPUT et OUTPUT, qui servent respectivement à stoquer les questions des client et les réponses de l'IA. Un callback est mis en place sur la queue OUTPUT afin d'envoyer en continue les réponses de l'IA aux clients concernés (en gardant l'id du socket). Ce système de gestion de queue permet donc de gérer les demandes des clients (en concurrence) au serveur IA qui est unique, afin de définir l'ordre de traitement des questions et de l'envoie des réponses.
