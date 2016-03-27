import sys
import argparse
import pprint
import os
import json
from kazoo.client import KazooClient
import errno

import cmd_memcached
import cmd_db
import cmd_client
import cmd_attr
import cmd_import
import cmd_alg

gdata = {
    'zk_client': None,
    'conf_data': None,
    'conf_path': os.path.expanduser("~/.seldon/seldon.conf"),
    'cmds': {
        'memcached' : cmd_memcached.cmd_memcached,
        'db' : cmd_db.cmd_db,
        'client' : cmd_client.cmd_client,
        'attr' : cmd_attr.cmd_attr,
        'import' : cmd_import.cmd_import,
        'alg' : cmd_alg.cmd_alg,
    }
}

def get_default_conf():
    return '''\
{
    "default_algorithms": {
        "assocRuleRecommender": {
            "config": []
        },
        "dynamicClusterCountsRecommender": {
            "config": []
        },
        "externalItemRecommendationAlgorithm": {
            "config": [
                {
                    "name": "io.seldon.algorithm.inclusion.itemsperincluder",
                    "value": 100000
                },
                {
                    "name": "io.seldon.algorithm.external.url",
                    "value": "http://127.0.0.1:5000/recommend"
                },
                {
                    "name": "io.seldon.algorithm.external.name",
                    "value": "example_alg"
                }
            ],
            "includers": [
                "recentItemsIncluder"
            ]
        },
        "globalClusterCountsRecommender": {
            "config": []
        },
        "itemCategoryClusterCountsRecommender": {
            "config": []
        },
        "itemClusterCountsRecommender": {
            "config": []
        },
        "itemSimilarityRecommender": {
            "config": []
        },
        "mfRecommender": {
            "config": []
        },
        "mostPopularRecommender": {
            "config": []
        },
        "recentItemsRecommender": {
            "config": []
        },
        "recentMfRecommender": {
            "config": [
                {
                    "name": "io.seldon.algorithm.general.numrecentactionstouse",
                    "value": "1"
                }
            ]
        },
        "semanticVectorsRecommender": {
            "config": []
        },
        "userTagAffinityRecommender": {
            "config": []
        }
    },
    "default_models": {
        "cluster-by-dimension": {},
        "matrix-factorization": {
            "config": {
                "activate": true,
                "alpha": 1,
                "days": 1,
                "inputPath": "%SELDON_MODELS%",
                "iterations": 5,
                "lambda": 0.01,
                "outputPath": "%SELDON_MODELS%",
                "rank": 30,
                "startDay": 1
            },
            "training": {
                "job_info": {
                    "cmd": "%SPARK_HOME%/bin/spark-submit",
                    "cmd_args": [
                        "--class",
                        "io.seldon.spark.mllib.MfModelCreation",
                        "--master",
                        "local[1]",
                        "%SELDON_SPARK_HOME%/target/seldon-spark-%SELDON_VERSION%-jar-with-dependencies.jar",
                        "--client",
                        "%CLIENT_NAME%",
                        "--zookeeper",
                        "%ZK_HOSTS%"
                    ]
                },
                "job_type": "spark"
            }
        },
        "semvec": {},
        "similar-items": {},
        "tagaffinity": {},
        "tagcluster": {}
    },
    "seldon_models": "~/.seldon/seldon-models",
    "seldon_spark_home": "~/seldon-server/offline-jobs/spark",
    "seldon_version": "0.93",
    "spark_home": "~/apps/spark",
    "zk_hosts": "localhost:2181",
    "zkroot": "~/.seldon/zkroot"
}
'''

def pp(o):
    p = pprint.PrettyPrinter(indent=4)
    p.pprint(o)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def dict_to_json(d, expand=False):
    return json.dumps(d, sort_keys=True, indent=4, separators=(',', ': ')) if expand else json.dumps(d, sort_keys=True, separators=(',',':'))

def json_to_dict(json_data):
    return json.loads(json_data)

def getOpts():
    parser = argparse.ArgumentParser(prog='seldon-cli', description='Seldon Cli')
    parser.add_argument('--version', action='store_true', help="print the version", required=False)
    parser.add_argument('--debug', action='store_true', help="debugging flag", required=False)
    parser.add_argument('--zk-hosts', help="the zookeeper hosts", required=False)
    parser.add_argument('--setup-config', action='store_true', help="setup the config and exit", required=False)
    parser.add_argument('-q', "--quiet", action='store_true', help="only display important messages, useful in non-interactive mode")
    parser.add_argument('args', nargs=argparse.REMAINDER) # catch rest (non-options) as args
    opts = parser.parse_args()
    return opts

def expand_conf():
    conf_data = gdata['conf_data']

    if conf_data != None:
        expansion_list = ["zkroot","seldon_models","spark_home","seldon_spark_home"]
        for expansion_item in expansion_list:
            conf_data[expansion_item] = os.path.expanduser(conf_data[expansion_item])

def create_default_conf():
    fpath = gdata['conf_path']
    if not os.path.isfile(fpath):
        default_conf = get_default_conf()
        mkdir_p(os.path.dirname(fpath))
        d = json_to_dict(default_conf)
        zkroot = os.path.expanduser(d["zkroot"])
        mkdir_p(zkroot)
        seldon_models = os.path.expanduser(d["seldon_models"])
        mkdir_p(seldon_models)
        default_conf = json.dumps(d, sort_keys=True, indent=4, separators=(',', ': '))
        f = open(fpath, 'w')
        f.write(default_conf)
        f.write('\n')
        f.close()
        print "Created conf file [{fpath}] with default settings.".format(**locals())
        sys.exit(0)
    else:
        print "Existing conf file [{fpath}] found.".format(**locals())

def check_conf():
    fpath = gdata['conf_path']
    if os.path.isfile(fpath):
        with open(fpath) as data_file:
            gdata["conf_data"] = json.load(data_file)

def start_zk_client(opts):
    zk_hosts = opts.zk_hosts
    if not opts.quiet:
        sys.stdout.write("connecting to "+zk_hosts)
    gdata["zk_client"] = KazooClient(hosts=zk_hosts)
    gdata["zk_client"].start()
    res = "SUCCEEDED" if gdata["zk_client"].connected else "FAILED"
    if not opts.quiet:
        print " [{res}]".format(**locals())

def stop_zk_client():
    if gdata["zk_client"].connected:
        gdata["zk_client"].stop()

def main():
    check_conf()
    expand_conf()
    opts = getOpts()
    if opts.setup_config:
        create_default_conf()
        sys.exit(0)

    # is the conf still not setup
    if gdata['conf_data'] == None:
        print "No config found, run with '--setup-config' to set it up."
        sys.exit(1)

    if opts.version == True:
        from seldon import __version__
        print __version__
        sys.exit(0)

    if len(opts.args) < 1:
        print "Need command"
        sys.exit(1)

    if opts.zk_hosts != None:
        gdata["conf_data"]["zk_hosts"] = opts.zk_hosts
    else:
        opts.zk_hosts = gdata["conf_data"]["zk_hosts"]

    cmd = opts.args[0]
    command_args = opts.args[1:]

    cmds = gdata['cmds']
    if cmds.has_key(cmd):
        start_zk_client(opts)
        command_data = {
                'conf_data' : gdata['conf_data'],
                'zkdetails' : {'zkroot': gdata['conf_data']['zkroot'], 'zk_client': gdata['zk_client']},
        }
        cmds[cmd](command_data, command_args)
        stop_zk_client()
    else:
        print "Invalid command[{}]".format(cmd)
        sys.exit(1)

if __name__ == '__main__':
    main()
