#!/usr/bin/env python3
import os
import yaml
import argparse
import json
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify
from prometheus_client import CollectorRegistry, Gauge, generate_latest

global perccli_path
global registry
global metrics

app = Flask("ESXi PERCCLI Exporter")

class PercMetrics():
    def __init__(self, username, password, host) -> None:
        self.registry = CollectorRegistry()
        self.namespace = "megaraid"
        
        self.username = username
        self.password = password
        self.host = host

        self.metrics = {
            # fmt: off
            "ctrl_info": Gauge(
                "controller_info",
                "MegaRAID controller info",
                ["controller", "model", "serial", "fwversion"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_temperature": Gauge(
                "temperature",
                "MegaRAID controller temperature",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_healthy": Gauge(
                "healthy",
                "MegaRAID controller healthy",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_degraded": Gauge(
                "degraded",
                "MegaRAID controller degraded",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_failed": Gauge(
                "failed",
                "MegaRAID controller failed",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_time_difference": Gauge(
                "time_difference",
                "MegaRAID time difference",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "bbu_healthy": Gauge(
                "battery_backup_healthy",
                "MegaRAID battery backup healthy",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "bbu_temperature": Gauge(
                "bbu_temperature",
                "MegaRAID battery backup temperature",
                ["controller", "bbuidx"], namespace=self.namespace, registry=self.registry,
            ),
            "cv_temperature": Gauge(
                "cv_temperature",
                "MegaRAID CacheVault temperature",
                ["controller", "cvidx"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_sched_patrol_read": Gauge(
                "scheduled_patrol_read",
                "MegaRAID scheduled patrol read",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_ports": Gauge(
                "ports",
                "MegaRAID ports",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_physical_drives": Gauge(
                "physical_drives",
                "MegaRAID physical drives",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_drive_groups": Gauge(
                "drive_groups",
                "MegaRAID drive groups",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "ctrl_virtual_drives": Gauge(
                "virtual_drives",
                "MegaRAID virtual drives",
                ["controller"], namespace=self.namespace, registry=self.registry,
            ),
            "vd_info": Gauge(
                "vd_info",
                "MegaRAID virtual drive info",
                ["controller", "DG", "VG", "name", "cache", "type", "state"],
                namespace=self.namespace, registry=self.registry,
            ),
            "pd_shield_counter": Gauge(
                "pd_shield_counter",
                "MegaRAID physical drive shield counter",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_media_errors": Gauge(
                "pd_media_errors",
                "MegaRAID physical drive media errors",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_other_errors": Gauge(
                "pd_other_errors",
                "MegaRAID physical drive other errors",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_predictive_errors": Gauge(
                "pd_predictive_errors",
                "MegaRAID physical drive predictive errors",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_smart_alerted": Gauge(
                "pd_smart_alerted",
                "MegaRAID physical drive SMART alerted",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_link_speed": Gauge(
                "pd_link_speed_gbps",
                "MegaRAID physical drive link speed in Gbps",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_device_speed": Gauge(
                "pd_device_speed_gbps",
                "MegaRAID physical drive device speed in Gbps",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_commissioned_spare": Gauge(
                "pd_commissioned_spare",
                "MegaRAID physical drive commissioned spare",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_emergency_spare": Gauge(
                "pd_emergency_spare",
                "MegaRAID physical drive emergency spare",
                ["controller", "enclosure", "slot"], namespace=self.namespace, registry=self.registry,
            ),
            "pd_info": Gauge(
                "pd_info",
                "MegaRAID physical drive info",
                [
                    "controller",
                    "enclosure",
                    "slot",
                    "disk_id",
                    "interface",
                    "media",
                    "model",
                    "DG",
                    "state",
                    "firmware",
                    "serial",
                ],
                namespace=self.namespace, registry=self.registry,
            ),
            # fmt: on
        }
    

    def main(self):
        """main"""
        data = self.get_storcli_json("/cALL show all J")
        
        valid_megaraid_drivers = ["megaraid_sas", "lsi_mr3"]

        try:
            # All the information is collected underneath the Controllers key
            data = data["Controllers"]

            for controller in data:
                response = controller["Response Data"]

                self.handle_common_controller(response)
                if response["Version"]["Driver Name"] in valid_megaraid_drivers:
                    self.handle_megaraid_controller(response)
                elif response["Version"]["Driver Name"] == "mpt3sas":
                    self.handle_sas_controller(response)
        except KeyError as e:
            print(e)
            pass

        return generate_latest(self.registry).decode()


    def handle_common_controller(self, response):
        controller_index = response["Basics"]["Controller"]

        self.metrics["ctrl_info"].labels(
            controller_index,
            response["Basics"]["Model"],
            response["Basics"]["Serial Number"],
            response["Version"]["Firmware Version"],
        ).set(1)

        # Older boards don't have this sensor at all ("Temperature Sensor for ROC" : "Absent")
        for key in ["ROC temperature(Degree Celcius)", "ROC temperature(Degree Celsius)"]:
            if key in response["HwCfg"]:
                self.metrics["ctrl_temperature"].labels(controller_index).set(
                    response["HwCfg"][key]
                )
                break


    def handle_sas_controller(self, response):
        controller_index = response["Basics"]["Controller"]

        self.metrics["ctrl_healthy"].labels(controller_index).set(
            response["Status"]["Controller Status"] == "OK"
        )
        self.metrics["ctrl_ports"].labels(controller_index).set(
            response["HwCfg"]["Backend Port Count"]
        )

        try:
            # The number of physical disks is half of the number of items in this dict. Every disk is
            # listed twice - once for basic info, again for detailed info.
            self.metrics["ctrl_physical_drives"].labels(controller_index).set(
                len(response["Physical Device Information"].keys()) / 2
            )
        except AttributeError:
            pass

        for key, basic_disk_info in response["Physical Device Information"].items():
            if "Detailed Information" in key:
                continue
            self.create_metrics_of_physical_drive(
                basic_disk_info[0],
                response["Physical Device Information"],
                controller_index,
            )


    def handle_megaraid_controller(self, response):
        controller_index = response["Basics"]["Controller"]

        if response["Status"]["BBU Status"] != "NA":
            # BBU Status Optimal value is 0 for normal, 8 for charging.
            self.metrics["bbu_healthy"].labels(controller_index).set(
                response["Status"]["BBU Status"] in [0, 8, 4096]
            )

        self.metrics["ctrl_degraded"].labels(controller_index).set(
            response["Status"]["Controller Status"] == "Degraded"
        )
        self.metrics["ctrl_failed"].labels(controller_index).set(
            response["Status"]["Controller Status"] == "Failed"
        )
        self.metrics["ctrl_healthy"].labels(controller_index).set(
            response["Status"]["Controller Status"] == "Optimal"
        )
        self.metrics["ctrl_ports"].labels(controller_index).set(
            response["HwCfg"]["Backend Port Count"]
        )
        self.metrics["ctrl_sched_patrol_read"].labels(controller_index).set(
            "hrs" in response["Scheduled Tasks"]["Patrol Read Reoccurrence"]
        )

        for cvidx, cvinfo in enumerate(response.get("Cachevault_Info", [])):
            if "Temp" in cvinfo:
                self.metrics["cv_temperature"].labels(controller_index, cvidx).set(
                    cvinfo["Temp"].replace("C", "")
                )

        for bbuidx, bbuinfo in enumerate(response.get("BBU_Info", [])):
            if "Temp" in bbuinfo:
                self.metrics["bbu_temperature"].labels(controller_index, bbuidx).set(
                    bbuinfo["Temp"].replace("C", "")
                )

        system_time = datetime.strptime(
            response["Basics"]["Current System Date/time"], "%m/%d/%Y, %H:%M:%S"
        )
        controller_time = datetime.strptime(
            response["Basics"]["Current Controller Date/Time"], "%m/%d/%Y, %H:%M:%S"
        )
        if system_time and controller_time:
            self.metrics["ctrl_time_difference"].labels(controller_index).set(
                abs(system_time - controller_time).seconds
            )

        # Make sure it doesn't crash if it's a JBOD setup
        if "Drive Groups" in response:
            self.metrics["ctrl_drive_groups"].labels(controller_index).set(
                response["Drive Groups"]
            )
            self.metrics["ctrl_virtual_drives"].labels(controller_index).set(
                response["Virtual Drives"]
            )

            for virtual_drive in response["VD LIST"]:
                vd_position = virtual_drive.get("DG/VD")
                if vd_position:
                    drive_group, volume_group = vd_position.split("/")[:2]
                else:
                    drive_group, volume_group = -1, -1

                self.metrics["vd_info"].labels(
                    controller_index,
                    drive_group,
                    volume_group,
                    virtual_drive["Name"],
                    virtual_drive["Cache"],
                    virtual_drive["TYPE"],
                    virtual_drive["State"],
                ).set(1)

        self.metrics["ctrl_physical_drives"].labels(controller_index).set(
            response["Physical Drives"]
        )

        if response["Physical Drives"] > 0:
            data = self.get_storcli_json("/cALL/eALL/sALL show all J")
            drive_info = data["Controllers"][controller_index]["Response Data"]
        for physical_drive in response["PD LIST"]:
            self.create_metrics_of_physical_drive(physical_drive, drive_info, controller_index)


    def create_metrics_of_physical_drive(
        self, physical_drive, detailed_info_array, controller_index
    ):
        enclosure, slot = physical_drive.get("EID:Slt").split(":")[:2]

        if enclosure == " ":
            drive_identifier = "Drive /c{0}/s{1}".format(controller_index, slot)
            enclosure = ""
        else:
            drive_identifier = "Drive /c{0}/e{1}/s{2}".format(
                controller_index, enclosure, slot
            )

        try:
            info = detailed_info_array[drive_identifier + " - Detailed Information"]
            state = info[drive_identifier + " State"]
            attributes = info[drive_identifier + " Device attributes"]
            settings = info[drive_identifier + " Policies/Settings"]

            self.metrics["pd_shield_counter"].labels(controller_index, enclosure, slot).set(
                state["Shield Counter"]
            )
            self.metrics["pd_media_errors"].labels(controller_index, enclosure, slot).set(
                state["Media Error Count"]
            )
            self.metrics["pd_other_errors"].labels(controller_index, enclosure, slot).set(
                state["Other Error Count"]
            )
            self.metrics["pd_predictive_errors"].labels(controller_index, enclosure, slot).set(
                state["Predictive Failure Count"]
            )
            self.metrics["pd_smart_alerted"].labels(controller_index, enclosure, slot).set(
                state["S.M.A.R.T alert flagged by drive"] == "Yes"
            )
            self.metrics["pd_link_speed"].labels(controller_index, enclosure, slot).set(
                attributes["Link Speed"].split(".")[0]
            )
            self.metrics["pd_device_speed"].labels(controller_index, enclosure, slot).set(
                attributes["Device Speed"].split(".")[0]
            )
            self.metrics["pd_commissioned_spare"].labels(controller_index, enclosure, slot).set(
                settings["Commissioned Spare"] == "Yes"
            )
            self.metrics["pd_emergency_spare"].labels(controller_index, enclosure, slot).set(
                settings["Emergency Spare"] == "Yes"
            )

            # Model, firmware version and serial number may be space-padded, so strip() them.
            self.metrics["pd_info"].labels(
                controller_index,
                enclosure,
                slot,
                physical_drive["DID"],
                physical_drive["Intf"],
                physical_drive["Med"],
                physical_drive["Model"].strip(),
                physical_drive["DG"],
                physical_drive["State"],
                attributes["Firmware Revision"].strip(),
                attributes["SN"].strip(),
            ).set(1)
        except KeyError as e:
            print(e)
            pass


    def get_storcli_json(self, storcli_args):
        """Get storcli output in JSON format."""
        # Check if storcli is installed and executable
        # if not (os.path.isfile(perccli_path) and os.access(perccli_path, os.X_OK)):
        #    raise SystemExit(1)

        perccli_cmd = (
            f"sshpass -p {self.password} ssh {self.username}@{self.host} '"
            + perccli_path
            + " "
            + storcli_args
            + "'"
        )

        proc = subprocess.Popen(
            perccli_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, _ = proc.communicate()
        data = stdout.decode()
        data = json.loads(data)

        if data["Controllers"][0]["Command Status"]["Status"] != "Success":
            raise SystemExit(1)
        return data


def load_config(file_path):
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    return config

@app.route("/metrics")
def metrics_route():
    target = request.args.get("target")
    if target and target in config["targets"]:
        username = config["targets"][target]["username"]
        password = config["targets"][target]["password"]
        host = target
        return PercMetrics(username, password, host).main()
    else:
        return jsonify({"message": "Credentials not found"}), 500

if __name__ == "__main__":
    config_file_path = os.environ.get("CONFIG_FILE_PATH", "config.yaml")
    perccli_path = os.environ.get("PERCCLI_FILE_PATH", "/opt/lsi/perccli/perccli")
    config = load_config(config_file_path)
    port = int(os.environ.get("PORT", 10424))
    app.run(host="0.0.0.0", port=port)
