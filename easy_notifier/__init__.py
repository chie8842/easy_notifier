from configparser import ConfigParser
import functools
import urllib3
import sys
import os
from datetime import datetime
import slackweb
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


def _get_config(*args, **kwargs):
    """_get_config
    get configurations from config file.
    default config file name is 'config.ini'.
    if you have cfg_file definition, it will used instead of default config.ini.
    """
    config = ConfigParser()

    cfg_file = ''
    if 'cfg_file' not in locals()['kwargs']:
        cfg_file = 'config.ini'
    else:
        cfg_file = kwargs['cfg_file']

    try:
        config.read(cfg_file)
        config = config['easy_notifier']
    except(RuntimeError, KeyError):
        print('failed to read {}'.format(cfg_file))
        config = {}
    return config


def _set_process_name(func, process_name):
    """_set_process_name
    If process_name is not set on configuration file,
    func.__name__ is used as the process_name

    :param func:
    :param process_name:
    """
    print(process_name)
    if len(process_name) == 0:
        process_name = func.__name__
    return process_name


def _get_hostname():
    """_get_hostname
    set hostname as the instance_name
    """
    return os.uname()[1]


def _get_instance_name_from_ec2_tag():
    """_get_instance_name_from_ec2_tag
    set Name tag of ec2 as the instance_name
    """
    import boto3
    http = urllib3.PoolManager()
    r = http.request('GET', 'http://169.254.169.254/latest/meta-data/instance-id')
    instance_id = r.data.decode('utf-8')
    ec2 = boto3.resource('ec2')
    my_instance = ec2.Instance(id=instance_id)

    instance_name = ''
    for tag in my_instance.tags:
        if tag['Key'] == 'Name':
            instance_name = tag['Value']

    if len(instance_name) == 0:
        instance_name = _get_hostname()

    return instance_name


def _get_instance_name_from_gce_tag():
    """_get_instance_name_from_gce_tag
    set Name tag of gce as the instance_name.
    """
    # TODO: integrate with google api client for python
    instance_name = _get_hostname()
    return instance_name


def _set_attachments(slack_id, contents, status, channel):
    """_set_attachments

    :param slack_id:
    :param contents:
    :param status:
    :param channel:
    """
    title, color, status_icon = _set_status(status)
    username = 'easy_notifier'
    icon_emoji = ':cherries:'
    text = '''
        <@{}> {}{}
        {}
    '''.format(slack_id, title, status_icon, contents)
    attachments = []
    attachment = {
            'text': text,
            'color': color,
            'channel': channel,
            'username': username,
            'icon_emoji': icon_emoji,
            'mrkdwn': True,
            }
    attachments.append(attachment)
    return attachments


def _set_status(status):
    """_set_status
    set notification title w.r.t. status.
    In addition, color and status icon which is used at slack notification is set, too.

    :param status:
    """
    title = ''
    status_icon = ''

    if status == 0:
        title = 'Process Succeeded'
        color = 'good'
        status_icon = ':ok_woman:'
    else:
        title = 'Process Failed'
        color = 'danger'
        status_icon = ':no_good:'
    return title, color, status_icon


def _set_contents(instance_name, process_name, result, start_time, finish_time):
    """_set_contents

    :param instance_name:
    :param process_name:
    :param result:
    :param start_time:
    :param finish_time:
    """
    contents = '''
        instance_name: {}
        process_name: {}
        start_time: {}
        finish_time: {}
        return: {}
    '''.format(instance_name, process_name, start_time, finish_time, result)
    return contents


def _notify_slack(incoming_webhook_url, attachments):
    """_notify_slack

    :param incoming_webhook_url:
    :param attachments:
    """
    slack = slackweb.Slack(url=incoming_webhook_url)
    slack.notify(attachments=attachments)


def _notify_mac(contents, status):
    """_notify_mac

    :param instance_name:
    :param process_name:
    :param status:
    :param result:
    :param start_time:
    :param finish_time:
    """
    import subprocess
    title, color, status_icon = _set_status(status)
    with_title = title

    applescript = '''
    display dialog "{}" ¬
    with title "{}" ¬
    with icon caution ¬
    buttons {{"OK"}}
    '''.format(contents, with_title)

    subprocess.call("osascript -e '{}'".format(applescript), shell=True)


def _notify_gmail(
        from_address,
        from_password,
        to_address,
        contents,
        status):
    """_notify_gmail

    :param from_address:
    :param from_password:
    :param to_address:
    :param contents:
    :param status:
    """
    msg = _gmail_create_message(from_address, to_address, contents, status)
    _gmail_send(from_address, from_password, to_address, msg)


def _gmail_create_message(from_address, to_address, contents, status):
    """_create_message

    :param from_address:
    :param to_address:
    :param body:
    """
    title, color, status_icon = _set_status(status)
    msg = MIMEText(contents)
    msg['Subject'] = title
    msg['From'] = from_address
    msg['To'] = to_address
    return msg


def _gmail_send(from_address, from_password, to_address, msg):
    """_send

    :param from_address:
    :param from_password:
    :param to_address:
    :param msg:
    """
    smtpobj = smtplib.SMTP('smtp.gmail.com', 587)
    smtpobj.ehlo()
    smtpobj.starttls()
    smtpobj.ehlo()
    smtpobj.login(from_address, from_password)
    smtpobj.sendmail(from_address, to_address, msg.as_string())
    smtpobj.close()

def easy_notifier(cfg_file='config.ini'):
    def _easy_notifier(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # TODO: get status of the process

            cfg_file = ''
            if 'cfg_file' not in locals()['kwargs']:
                cfg_file = 'config.ini'
            else:
                cfg_file = kwargs['cfg_file']

            config = _get_config(cfg_file=cfg_file)
            if len(config) == 0:
                sys.exit(1)

            env = config['env']
            notify_slack = config.getboolean('notify_slack')
            notify_mac = config.getboolean('notify_mac')
            notify_gmail = config.getboolean('notify_gmail')
            print('func')
            print(func)
            process_name = _set_process_name(func, config['process_name'])

            if notify_mac and os.uname()[0] != 'Darwin':
                print('notify_mac parameter is variable at only MacOSX')

            instance_name = ''
            if env == 'ec2':
                instance_name = _get_instance_name_from_ec2_tag()
            elif env == 'gce':
                instance_name = _get_instance_name_from_gce_tag()
            elif env == 'local':
                instance_name = _get_hostname()

            if len(instance_name) == 0:
                sys.exit(1)

            result = ''
            start_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            try:
                result = func(*args, **kwargs)
                status = 0
            except:
                status = 1

            finish_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

            contents = _set_contents(
                    instance_name,
                    process_name,
                    result,
                    start_time,
                    finish_time)

            if notify_slack:
                incoming_webhook_url = config['incoming_webhook_url']
                slack_id = config['slack_id']
                channel = config['channel']
                attachments = _set_attachments(
                        slack_id,
                        contents,
                        status,
                        channel)
                _notify_slack(incoming_webhook_url, attachments)

            if notify_gmail:
                from_address = config['from_address']
                from_password = config['from_password']
                to_address = config['to_address']
                _notify_gmail(
                        from_address,
                        from_password,
                        to_address,
                        contents,
                        status)

            if notify_mac and os.uname()[0] == 'Darwin':
                _notify_mac(
                        contents,
                        status)

            return result

        return wrapper
    return _easy_notifier
