from xmlrpc.server import SimpleXMLRPCServer
from random import randint
import threading
import xmlrpc.client as xmlrpclib
import operator
import argparse
import logging
import queue as Queue
import sys
import os

HISTORY_LENGTH = 500


class AuthLogClient(threading.Thread):
    def __init__(self, model):
        super().__init__()
        self.daemon = True
        self.model = model
        self.eventHistory = []
        self.eventCount = 0
        self.logger = logging.getLogger("AuthLogClient")

        self.host, self.port = 'localhost', randint(5000, 20000)
        self.queues = []
        self.server = SimpleXMLRPCServer(
            (self.host, self.port),
            logRequests=False,
            allow_none=True
        )

    def subscribe(self):
        self.start()

    def unsubscribe(self):
        try:
            self.model.unsubscribe(self.host, self.port)
        except Exception:
            pass
        self.server.server_close()

    def getEvents(self, queue):
        self.queues.append(queue)

        for eventData in self.eventHistory:
            queue.put(eventData)

        try:
            while True:
                try:
                    yield queue.get(block=True, timeout=1)
                except Queue.Empty:
                    pass
                except GeneratorExit:
                    raise
                except Exception:
                    self.logger.critical("Error generating events!", exc_info=True)
                    raise
        finally:
            self.removeQueue(queue)

    def removeQueue(self, queue):
        if queue in self.queues:
            self.queues.remove(queue)

    def event(self, data):
        self.eventCount += 1
        for queue in self.queues:
            queue.put(data)
        return True  # XML-RPC requires a response

    def run(self):
        self.model.subscribe(self.host, self.port)
        self.server.register_function(self.event)

        try:
            self.logger.info(f"Subscribed to auth.log events! ({self.host}:{self.port})")

            self.eventHistory = self.model.getEventHistory(HISTORY_LENGTH)
            self.eventCount += self.model.getEventCount() - len(self.eventHistory)

            self.logger.info(f"Fetched History: {len(self.eventHistory)}")
            self.logger.info(f"Total Events: {self.eventCount}")

            self.server.serve_forever()

        except KeyboardInterrupt:
            print("Exiting")
        except Exception:
            self.logger.critical("Error while listening for events from server!", exc_info=True)
        finally:
            self.unsubscribe()


class AuthLogModel(object):
    def __init__(self):
        self.server = xmlrpclib.ServerProxy('http://localhost:7080/')

        if self.server.ping() != "pong":
            raise RuntimeError("Faulty Server!")

        self.getHostMessages = self.server.getHostMessages
        self.getHostInfo = self.server.getHostInfo
        self.subscribe = self.server.subscribe
        self.unsubscribe = self.server.unsubscribe
        self.getEventHistory = self.server.getEventHistory
        self.getEventCount = self.server.getEventCount


class AuthLogView(object):
    def showSummary(self, hostMessages, hostInfo):
        for host in sorted(hostMessages.keys()):
            hostInfoStr = ": "
            try:
                hostObj = hostInfo[host]
                locTemplate = "%s, %s (%s)"
                location = locTemplate % (
                    hostObj["city"],
                    hostObj["region"],
                    hostObj["country"]
                )
                hostInfoStr += location + ": " + hostObj["org"]
            except KeyError:
                hostInfoStr += "No info."

            print(host + hostInfoStr)

            sortedmessageCounts = sorted(
                hostMessages[host].items(),
                key=operator.itemgetter(1),
                reverse=True
            )

            print("    %-5s %s" % ("Count", "Message"))
            print("    %-5s %s" % ("-----", "-" * 50))
            for message, count in sortedmessageCounts:
                print("    %5s: %s" % (str(count), repr(message)))
            print()

        print()
        print(len(hostMessages.keys()), "Hosts")

    def showByCountry(self, hostMessages, hostInfo):
        hostDetails = {}

        for host in sorted(hostMessages.keys()):
            hostItems = []
            for item in ("country", "region", "city", "org"):
                hostValue = "??"
                hostObj = hostInfo[host]
                if item in hostObj and len(hostObj[item].strip()) > 0:
                    hostValue = hostObj[item]
                hostItems.append(hostValue)

            hostItems = tuple(hostItems)

            if hostItems not in hostDetails:
                hostDetails[hostItems] = set()

            hostDetails[hostItems].add(host)

        for key in sorted(hostDetails.keys(), key=operator.itemgetter(0, 1, 2)):
            (country, region, city, org) = key
            hosts = hostDetails[key]

            hostInfoStr = "%-2s: %15s, %-20s %-50s %-30s" % (
                country,
                city,
                region,
                org,
                ", ".join(sorted(hosts))
            )

            print(hostInfoStr)


class AuthLogClientController(object):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Query /var/log/auth.log listener.',
            usage='''app [<command>] [<args>]

Valid commands:
   summary    Show a summary of hosts in the auth log (Default)
   country    Show the breakdown of entries by country
   subscribe  Show json events as they occur in realtime
'''
        )

        parser.add_argument('command', nargs='?', default="summary")

        args = parser.parse_args(sys.argv[1:2])

        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)

        self.presenter = AuthLogView()
        self.model = AuthLogModel()

        getattr(self, args.command)()

    def summary(self):
        hostMessages = self.model.getHostMessages()
        hostInfo = self.model.getHostInfo()
        self.presenter.showSummary(hostMessages, hostInfo)

    def country(self):
        hostMessages = self.model.getHostMessages()
        hostInfo = self.model.getHostInfo()
        self.presenter.showByCountry(hostMessages, hostInfo)

    def subscribe(self):
        subscriber = AuthLogClient(self.model)
        subscriber.subscribe()

        q = Queue.Queue()

        try:
            for event in subscriber.getEvents(q):
                print(event)
        except KeyboardInterrupt:
            pass
        finally:
            print("Unsubscribing...")
            subscriber.unsubscribe()
            print("Done!")

        print("Exiting.")


if __name__ == "__main__":
    AuthLogClientController()
