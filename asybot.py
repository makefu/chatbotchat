#! /usr/bin/env python
#
BOT_VERSION= "Chatbot Version 1"

from chatterbotapi import ChatterBotFactory, ChatterBotType
factory = ChatterBotFactory()

from asynchat import async_chat as asychat
from asyncore import loop
from socket import AF_INET, SOCK_STREAM,gethostname
from signal import SIGALRM, signal, alarm
from datetime import datetime as date, timedelta
import shlex
from time import sleep,time
from sys import exit
from re import split, search
from textwrap import TextWrapper
from time import time

import logging,logging.handlers
log = logging.getLogger('asybot')
base_delay = 2
CPS = 7.5


hdlr = logging.handlers.SysLogHandler(facility=logging.handlers.SysLogHandler.LOG_DAEMON)
formatter = logging.Formatter( '%(filename)s: %(levelname)s: %(message)s')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)

# s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]//g -- removes color codes


class asybot(asychat):
  def __init__(self, server, port, nickname, targets,bottype,probability, **kwargs):
    asychat.__init__(self)

    if  bottype == "cleverbot":
      self.botfactory = factory.create(ChatterBotType.CLEVERBOT)
    elif bottype == "jabberwacky" :
      self.botfactory = factory.create(ChatterBotType.JABBERWACKY)
    elif bottype == "pandorabots":
      self.botfactory = factory.create(ChatterBotType.PANDORABOTS,"c7068fbf3e344abf")
    elif bottype == "twssbot":
      self.botfactory = factory.create(ChatterBotType.TWSSBOT)
    else:
      log.error("do not know bottype %s" % bottype)
      exit(1)

    self.bot = self.botfactory.create_session()
    self.probability = probability
    self.server = server
    self.port = port
    self.nickname = nickname
    self.targets = targets
    self.username = kwargs['username'] if 'username' in kwargs else nickname
    self.hostname = kwargs['hostname'] if 'hostname' in kwargs else nickname
    self.ircname = kwargs['ircname'] if 'ircname' in kwargs else nickname
    self.realname = kwargs['realname'] if 'realname' in kwargs else nickname
    log.info("This is " + BOT_VERSION)
    log.info("Probability : " + str(probability))
    log.info("nick : " + str(nick))
    log.info("Bottype: " + str(bottype))
    self.data = ''
    self.set_terminator('\r\n')
    self.create_socket(AF_INET, SOCK_STREAM)
    self.connect((self.server, self.port))
    self.wrapper = TextWrapper(subsequent_indent=" ",width=400)

    # When we don't receive data for alarm_timeout seconds then issue a
    # PING every hammer_interval seconds until kill_timeout seconds have
    # passed without a message.  Any incoming message will reset alarm.
    self.alarm_timeout = 300
    self.hammer_interval = 10
    self.kill_timeout = 360
    signal(SIGALRM, lambda signum, frame: self.alarm_handler())
    self.reset_alarm()


  def reset_alarm(self):
    self.last_activity = date.now()
    alarm(self.alarm_timeout)

  def alarm_handler(self):
    delta = date.now() - self.last_activity
    if delta > timedelta(seconds=self.kill_timeout):
      log.error('No data for %s.  Giving up...' % delta)
      exit(2)
    else:
      log.error('No data for %s.  PINGing server...' % delta)
      self.push('PING :%s' % self.nickname)
      alarm(self.hammer_interval)

  def collect_incoming_data(self, data):
    self.data += data

  def found_terminator(self):
    log.debug('<< %s' % self.data)

    message = self.data
    self.data = ''

    _, prefix, command, params, rest, _ = \
        split('^(?::(\S+)\s)?(\S+)((?:\s[^:]\S*)*)(?:\s:(.*))?$', message)
    params = params.split(' ')[1:]
    #print([prefix, command, params, rest])

    if command == 'PING':
      self.push('PONG :%s' % rest)
      log.debug("Replying to servers PING with PONG :%s" %rest)

    elif command == 'PRIVMSG':
      self.on_privmsg(prefix, command, params, rest)

    elif command == '433':
      # ERR_NICKNAMEINUSE, retry with another name
      _, nickname, int, _ = split('^.*[^0-9]([0-9]+)$', self.nickname) \
          if search('[0-9]$', self.nickname) \
          else ['', self.nickname, 0, '']
      self.nickname = nickname + str(int + 1)
      self.handle_connect()

    self.reset_alarm()

  def push(self, message):
    log.debug('>> %s' % message)
    asychat.push(self, message + self.get_terminator())

  def handle_connect(self):
    self.push('NICK %s' % self.nickname)
    self.push('USER %s %s %s :%s' %
        (self.username, self.hostname, self.server, self.realname))
    self.push('JOIN %s' % ','.join(self.targets))

  def on_privmsg(self, prefix, command, params, rest):
    def PRIVMSG(text):
      for line in self.wrapper.wrap(text):
        msg = 'PRIVMSG %s :%s' % (','.join(params), line)
        self.push(msg)
        sleep(1)

    def ME(text):
      PRIVMSG('ACTION ' + text + '')

    _from = prefix.split('!', 1)[0]

    from random import random
    if random() < self.probability:
      try:
        # delay
        log.info("%s will answer to '%s'"%(self.nickname,rest))
        now = time()
        answer = str(self.bot.think(rest))
        timetosleep = now + base_delay  - time() + len(answer) / CPS
        log.debug ("sleeping for %f seconds" % timetosleep)
        if (timetosleep > 0):sleep(timetosleep)
        PRIVMSG(answer)
      except Exception as e:
        log.error(str(e))
    else:
      log.info("%s will not answer to '%s', probability check failed" % (self.nickname,rest))
      


# retrieve the value of a [singleton] variable from a tinc.conf(5)-like file
def getconf1(x, path):
  from re import findall
  pattern = '(?:^|\n)\s*' + x + '\s*=\s*(.*\w)\s*(?:\n|$)'
  y = findall(pattern, open(path, 'r').read())
  if len(y) < 1:
    raise AttributeError("len(getconf1('%s', '%s') < 1)" % (x, path))
  if len(y) > 1:
    y = ' '.join(y)
    raise AttributeError("len(getconf1('%s', '%s') > 1)\n  ====>  %s"
        % (x, path, y))
  return y[0]

if __name__ == "__main__":
  from os import environ as env
  from sys import exit
  lol = logging.DEBUG if env.get('debug',False) else logging.INFO
  logging.basicConfig(level=lol)
  try: 
    name = getconf1('Name', '/etc/tinc/retiolum/tinc.conf')
    hostname = '%s.retiolum' % name
  except:
    name = gethostname()
    hostname = name
  nick = str(env.get('nick', name))
  host = str(env.get('host', 'supernode'))
  port = int(env.get('port', 6667))
  probability = float(env.get('probability', 0.5))

  target = str(env.get('target', '#retiolum'))
  log.info('=> irc://%s@%s:%s/%s' % (nick, host, port, target))

  from getpass import getuser
  bottype=  env.get('bottype',"cleverbot")

  asybot(host, port, nick, [target], username=getuser(),
      ircname='//Reaktor running at %s' % hostname,
      hostname=hostname,bottype=bottype,probability=probability)

  loop()
