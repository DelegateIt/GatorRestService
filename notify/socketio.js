
var express = require('express');
var app = express();
var http = require('http').Server(app);
var bodyParser = require('body-parser');
var io = require('socket.io')(http, {
    pingTimeout: 50000
});
var gator = require('./gator.js');
var port = gator.config.notifier_host.bind_port;

app.use(bodyParser.json());

//Add IP to transaction update handler
gator.updateHandler(function(err, resp) {
    console.log("Recveived response trying to update notifer handlers", err, resp);
});

app.get('/', function(req, res){
    res.send('gator web socket server');
});

app.post('/transaction_change', function(req, res){
    var transaction = req.body.transaction;
    console.log("Notifying listeners of change to transaction", transaction.uuid);
    io.to(transaction.uuid).emit(transaction.uuid, transaction);
    res.end(JSON.stringify({'result': 0}));
});

io.on('connection', function(socket){
    socket.on('register_transaction', function (data) {
        socket.join(data['transaction_uuid']);
        console.log('registering transaction', data);
    });
});

http.listen(port, function(){
    console.log('listening on *:' + port);
});
