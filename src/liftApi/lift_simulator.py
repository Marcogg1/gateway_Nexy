'''
testing device twin properties.reporting from lift simulator
simuate_lift_operation is report two properties to device_twin->reporting
report_temperature_loop is reporting temperature every minute and setting the result on device_twin->reporting
'''

from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.event_sender import EventSender
import random
import asyncio
import json
import time
import logging
from azure.iot.device import Message

# Setup logging
logger = logging.getLogger(__name__)

class LiftSimulator:
    def __init__(self, reporter: DeviceTwinReporter, event_sender: EventSender | None = None) -> None:
        self.reporter = reporter
        self.event_sender = event_sender

    async def simulate_lift_operation(self):
        # Simulate lift operations and report relevant properties
        await self.reporter.report_property("lift.status", "operational")
        await self.reporter.report_property("lift.currentFloor", 1)
        # Add more simulation logic as needed

    async def report_temperature_loop(self):

        while True:
            # Simulera temperaturvärde
            temperature = round(20 + random.uniform(-2, 2), 2)
            await self.reporter.report_property("temperature", temperature)
            logger.info(f"Reported temperature: {temperature}°C")
            await asyncio.sleep(60)  # Vänta 1 minut

    async def send_parameter_data(self):
        while True:
            parameter = random.randint(1,100)
            parameter_value = random.randint(1,1000)
            ts = str(int(time.time()))
            payload = {
                "data": [
                    {
                        "timestamp": ts,
                        "value": parameter_value,
                        "parameter": parameter
                    }
                ],
                "error":"",
                "event": "la.parameters.update",
                "source": "la.parameter.polling"
                }
            
            #return payload
            await asyncio.sleep(5)  # Vänta 5 sekunder mellan sändningar

            if self.event_sender:
                await self.event_sender.send_event(payload)
            else:
                logger.warning("EventSender not configured; skipping send")

