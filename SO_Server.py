# A simple python websocket server for communication with the SimpleOSC.js library.
# using tornado, a socket server module for python
# translates OSC messages packaged in JSON and sent over websockets into plain old OSC
# Using pythonosc: https://github.com/attwad/python-osc
# Docs: https://python-osc.readthedocs.io/en/latest/

import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.template
import json
from pythonosc import udp_client
from pythonosc import osc_server
from pythonosc import dispatcher
import argparse
import asyncio

# A clunky JSON to OSC mapping is done here
# for more sophisticated OSC see Colin Clark's osc.js library
#  https://github.com/colinbdclark/osc.js/
class WSHandler(tornado.websocket.WebSocketHandler):
    osc_client = None
    osc_serv = None
    osc_dispatcher = None
    singleton = None
    server_out = ("127.0.0.1", 57120)
    server_in = ("127.0.0.1", 9191)
    allowed_origins = ["http://localhost", "http://localhost:4000", "http://127.0.0.1", "http://127.0.0.1:4000", "null", "file://"];
    echo = False

    def check_origin(self, origin):
        if origin in WSHandler.allowed_origins:
            print("MSG ALLOWED, from origin", origin)
            return 1
        else:
            print("MSG DENIED, from origin", origin)
            return 0

    def open(self):
        print('Websockets connection opened with browser!')
        WSHandler.singleton = self
        osc_client = WSHandler.osc_client
        print('sending test message to browser and client...')
        osc_client.send_message("/browser/status", "testing")

        # OSC-like format
        # JSON: {address: oscaddr, args: [{type:type, value:val},...]}
        self.write_message(
            {"address": "/server/status",
            "args": [
                {
                    "type": "s",
                    "value": "SimpleOSC Server says hello! Handshakes..."
                }
            ]})
        osc_client.send_message("/browser/status", "Connection to Browser Successful")
        print("Sent message /browser/status")

    # Callback used by OSC server when a message comes in
    # See https://python-osc.readthedocs.io/en/latest/dispatcher.html
    def osc_message(addr, *osc_args) -> None:
        print("Recieved {} with args {}".format(addr, osc_args))
        if WSHandler.singleton is not None:
            args = []
            for arg in osc_args:
                argtype = type(arg)
                if argtype == int:
                    argtype = "i"
                elif argtype == float:
                    argtype = "f"
                elif argtype == str:
                    argtype = "s"
                elif argtype == list:
                    argtype = "a"
                elif argtype == object:
                    argtype = "o"
                else: # default to b/binary ?
                    argtype = "b"
                args.append({"type": argtype, "value": arg})
            WSHandler.singleton.write_message({
                "address": addr,
                "args": args
            })
            print("Sent to browser {} {}".format(addr, args))

        # TODO: forward to the browser....

    # Incoming json message from the browser
    def on_message(self, message):
        parsed = json.loads(message)
        address = parsed['address'];
        args = parsed['args'];
        echoargsmsg = [{"type": "s", "value": address}]
        oscargs = []
        for item in args:
            echoargsmsg.append(item)
            val = item['value']
            if type(val) == list:
                val = ','.join(str(x) for x in val)
            oscargs.append(val)


        if WSHandler.echo:
            echo = {"address": "/server/echo", "args": echoargsmsg}
            self.write_message(json.dumps(echo))

        print('received:', parsed)
        print('args are: ', type(parsed['args']))

        # Send unpackaged OSC message to client software (e.g. SuperCollider)
        WSHandler.osc_client.send_message(address, oscargs)

    def on_close(self):
        print( 'connection closed...')

def make_app():
    return tornado.web.Application([
        (r"/interface", WSHandler)
    ])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-send-ip", default="127.0.0.1", help="The IP to send OSC to")
    parser.add_argument("-send-port", type=int, default=57120, help="The port to send OSC to")
    parser.add_argument("-rcv-ip", default="127.0.0.1", help="The OSC IP to listen to")
    parser.add_argument("-rcv-port", type=int, default=9191, help="The OSC port to listen to")
    parser.add_argument("-ws-port", type=int, default=8080, help="The websockets port listening for connection from a browser")
    parser.add_argument("-origin", default="https://anatomiesofintelligence.github.io", help="Allowed client URL")
    parser.add_argument("-echo", type=bool, default=False, help="Enable server echo")
    clargs = parser.parse_args()
    WSHandler.server_out = (clargs.send_ip, clargs.send_port)
    WSHandler.server_in = (clargs.rcv_ip, clargs.rcv_port)
    WSHandler.allowed_origins.append(clargs.origin)
    WSHandler.echo = clargs.echo

    app = make_app()
    app.listen(clargs.ws_port)
    print("Waiting for websockets connection on port {} .... ".format(clargs.ws_port))

    WSHandler.osc_client = udp_client.SimpleUDPClient(WSHandler.server_out[0], WSHandler.server_out[1])
    print('Sending UDP/OSC messages to {}: {} ...'.format(WSHandler.server_out[0], WSHandler.server_out[1]))

    WSHandler.osc_dispatcher = dispatcher.Dispatcher()
    WSHandler.osc_dispatcher.set_default_handler(WSHandler.osc_message)
    WSHandler.osc_serv = osc_server.AsyncIOOSCUDPServer(WSHandler.server_in, WSHandler.osc_dispatcher, asyncio.get_event_loop())
    WSHandler.osc_serv.serve()
    print("Listening for OSC messages on {}: {} ...".format(WSHandler.server_in[0], WSHandler.server_in[1]))

    tornado.ioloop.IOLoop.instance().start()
