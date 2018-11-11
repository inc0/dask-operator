from kubernetes import client, config, watch
import threading
import yaml
from pprint import pprint


namespace = "default"

class DaskJob(object):
    def __init__(self, name, uid, spec):
        self.name = name
        self.uid = uid
        self.spec = spec

    def ensure_pods_exist(self):
        api = client.CoreV1Api(client.ApiClient())
        existing_pods = api.list_pod_for_all_namespaces(label_selector="daskjob={}".format(self.name)).items

        expected_pods_prefix = "daskjob-" + self.name + "-{role}"
        roles = ["master", "scheduler"]
        roles.extend(["worker-{idx}".format(idx=idx) for idx in range(int(self.spec["workers"]["count"]))])
        expected_pod_names = [expected_pods_prefix.format(role=role) for role in roles]
        existing_pod_names = [p.metadata.name for p in existing_pods]
        pods_to_create = set(expected_pod_names) - set(existing_pod_names)

        scheduler_hostname = "daskjob-" + self.name + "-scheduler"
        for p in pods_to_create:
            pod = {
                "metadata": {
                    "name": p,
                    "labels": {"daskjob": self.name}
                }
            }
            if "master" in p:
                pod["spec"] = self.spec["master"]["template"]["spec"]
            if "scheduler" in p:
                pod["spec"] = self.spec["scheduler"]["template"]["spec"]
                pod["spec"]["hostname"] = scheduler_hostname
            if "worker" in p:
                pod["spec"] = self.spec["workers"]["template"]["spec"]
            pod["spec"]["containers"][0]["env"] = [{"name": "DASK_SCHEDULER", "value": scheduler_hostname}]
            api.create_namespaced_pod(namespace="default", body=pod)

    def ensure_pods_missing(self):
        return None


class DaskJobProcessor(threading.Thread):
    def __init__(self, event):
        self.event = event
        threading.Thread.__init__(self)

    def run(self):
        pprint(self.event)
        dask_job = DaskJob(
            self.event['object']['metadata']['name'],
            self.event['object']['metadata']['uid'],
            self.event['object']['spec'],
        )
        if self.event['type'] == 'ADDED':
            dask_job.ensure_pods_exist()
        elif self.event['type'] == 'DELETED':
            dask_job.ensure_pods_missing()


def main():
    config.load_incluster_config()

    group = "kubeflow.org"
    version = "v1alpha1"
    plural = "daskjobs"
    api = client.CustomObjectsApi(client.ApiClient())
    w = watch.Watch()
    for event in w.stream(api.list_namespaced_custom_object, group, version, namespace, plural, watch=True):
        DaskJobProcessor(event).start()

if __name__ == '__main__':
    main()
