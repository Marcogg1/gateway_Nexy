from cloudApi.device_twin_reported import DeviceTwinReporter
import random
import asyncio

class LiftSimulator:
    def __init__(self, reporter: DeviceTwinReporter) -> None:
        self.reporter = reporter

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
            print(f"Reported temperature: {temperature}°C")
            await asyncio.sleep(60)  # Vänta 1 minut
