# encoding: UTF-8

# 引数の処理はここを参考にした：https://qiita.com/oohira/items/308bbd33a77200a35a3d

import argparse
import roamon_diff_checker
import subprocess
import os
import logging
from pyfiglet import Figlet

# ログ関係の設定 (適当)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ファイルの保存先
dir_path_data = "/Users/user1/temp/test"
file_path_vrps = os.path.join(dir_path_data, "vrps.csv")
file_path_rib = os.path.join(dir_path_data, "ip-as_rib.list")

# ロゴの描画
f = Figlet(font='slant')
print(f.renderText('roamon'))


# getサブコマンドの実際の処理を記述するコールバック関数
def command_get(args):
    print(args)

    # RIBのデータ取得
    if args.all or args.bgp:
        # TODO: 最新のRIBファイルを自動で選んでダウンロードできるようにする。現在は固定値。
        # RIBファイルのダウンロード
        subprocess.check_output(
            "wget http://archive.routeviews.org/bgpdata/2020.01/RIBS/rib.20200114.0200.bz2 -P " + dir_path_data,
            shell=True)
        # MRTフォーマットをパースし、PrefixとAS_PATHの列を取り出し、経路集約された部分を取り除いてOrigin ASを抜き出し、最終的に PrefixとOriginASがならぶCSVにする
        subprocess.check_output(
            "time bgpdump -Hm -t dump rib.20200114.0200.bz2 | cut -d \| -f6,7 | tr '\|' ' ' | sed s/\{.*\}// | awk '{print ($1),($NF)}' | tr ' ' ',' > " + file_path_rib,
            shell=True)
        logger.debug("finish fetch rib")

    # VRPs (Verified ROA Payloads)の取得
    if args.all or args.roa:
        # 入手したTALを永続化する準備
        subprocess.check_output(
            "sudo docker volume create routinator-tals",
            shell=True)
        # TALを入手
        subprocess.check_output(
            "sudo docker run --rm -v routinator-tals:/home/routinator/.rpki-cache/tals \
    nlnetlabs/routinator init -f --accept-arin-rpa",
            shell=True)
        # routinator起動
        subprocess.check_output(
            "sudo docker run -d --rm --name routinator -v routinator-tals:/home/routinator/.rpki-cache/tals nlnetlabs/routinator",
            shell=True)
        # routinatorでROAを取得 & 検証してVRPのリストを得る
        subprocess.check_output(
            "sudo docker exec -it routinator /bin/sh -c 'routinator vrps 2>/dev/null | tail -n +2' > " + file_path_vrps,
            shell=True)
        # routinatorのコンテナを止める(と同時に消える)
        subprocess.check_output(
            "sudo docker stop routinator",
            shell=True)
        logger.debug("finish fetch vrps")


# 検証サブコマンド　checkのとき呼ばれる関数
def command_check(args):
    print(args)
    data = roamon_diff_checker.load_all_data(file_path_vrps, file_path_rib)
    if args.asns is None:
        roamon_diff_checker.check_all_asn_in_vrps(data["vrps"], data["rib"])
    else:
        roamon_diff_checker.check_specified_asn(data["vrps"], data["rib"], args.asns)


def command_help(args):
    print(parser.parse_args([args.command, '--help']))
    # TODO: ヘルプをうまくやる


# コマンドラインパーサーを作成
parser = argparse.ArgumentParser(description='ROA - BGP Diff command !')
subparsers = parser.add_subparsers()

# get コマンドの parser を作成
parser_add = subparsers.add_parser('get', help='see `get -h`')
parser_add.add_argument('--all', action='store_true', help='specify retrieve type ALL (default)')
parser_add.add_argument('--roa', action='store_true', help='specify retrieve type only ROA')
parser_add.add_argument('--bgp', action='store_true', help='specify retrieve type only BGP')
parser_add.set_defaults(handler=command_get)

# check コマンドの parser を作成
parser_commit = subparsers.add_parser('check', help='see `check -h`')
parser_commit.add_argument('--asns', nargs='*', help='specify target ASNs (default: ALL)')
parser_commit.set_defaults(handler=command_check)

# help コマンドの parser を作成
parser_help = subparsers.add_parser('help', help='see `help -h`')
parser_help.add_argument('command', help='command name which help is shown')
parser_help.set_defaults(handler=command_help)

# コマンドライン引数をパースして対応するハンドラ関数を実行
args = parser.parse_args()
if hasattr(args, 'handler'):
    args.handler(args)
else:
    # 未知のサブコマンドの場合はヘルプを表示
    parser.print_help()
