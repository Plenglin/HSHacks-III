import math
import random
import threading
import time

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, send

import pymunk
from pymunk.vec2d import Vec2d

app = Flask(__name__)

players = []

room = None

BOOST_FORCE = 200.0
NORMAL_FORCE = 50.0
BRAKE_FRICTION = 0.1
FRICTION = 20
MAX_SPEED = 250.0
MIN_SPEED = 5
PLAYER_MASS = 1.0


class Player:

	def __init__(self, socket_id, room, body):
		self.socket_id = socket_id
		self.room = room
		self.body = body

		self.boosting = False
		self.boost_left = 3
		self.braking = False

	def get_pos(self):
		return self.body.position

	@property
	def rotation(self):
		return self.body.angle

	@rotation.setter
	def rotation(self, val):
		self.body.angle = val

class GameRoom:
	
	def __init__(self, players):
		super(GameRoom, self).__init__()
		self.players = players[:]
		self.space = pymunk.Space()
	
	def update(self, dt, socketio):

		for p in self.players:
			force = NORMAL_FORCE * Vec2d.unit()
			force.angle = p.rotation
			p.body.velocity += force/p.body.mass
			p.body.angular_velocity = 0

		for body in self.space.bodies:
			speed = body.velocity.get_length()
			if speed > 0:
				fricDir = -body.velocity.normalized()
				fricAmount = body.mass * FRICTION
				frictionForce = fricDir * fricAmount * dt
				if speed < MIN_SPEED:
					body.velocity = Vec2d.zero()
				else:
					body.velocity += frictionForce/body.mass
			if body.velocity.get_length() > MAX_SPEED:
				body.velocity = MAX_SPEED * body.velocity.normalized()

		self.space.step(dt)
		socketio.emit('entities', self.getEncodedPositions(), callback=lambda: print('asdf'))

	def getEncodedPositions(self):
		return [
			{
				'id': player.socket_id,
				'x': player.get_pos().x,
				'y': player.get_pos().y,
				'direction': player.rotation,
				'isBoosting': player.boosting,
				'boostRemaining': player.boost_left,
				'color': 'red'
			} for player in self.players
		]

	def player_by_sid(self, sid):
		for p in self.players:
			if p.socket_id == sid:
				return p
		return None

	def createPlayer(self, socket_sid):
		body = pymunk.Body(PLAYER_MASS, 1666)
		front_physical = pymunk.Poly(body, offsetBox(15, 0, 30, 60), radius=5.0)
		front_physical.elasticity = 1.5
		back_physical = pymunk.Poly(body, offsetBox(-45, 0, 90, 60), radius=5.0)
		back_physical.elasticity = 3.0
		back_sensor = pymunk.Poly(body, offsetBox(-45, 0, 100, 70), radius=5.0) 
		back_sensor.contact = True
		body.position = 100*random.random(), 100*random.random()
		body.angle = 2*math.pi*random.random()
		self.space.add(body, front_physical, back_physical, back_sensor)
		self.players.append(Player(socket_sid, self, body))

	def removePlayer(self, sid):
		for p in self.players:
			if p.socket_id == sid:
				for s in p.body.shapes:
					self.space.remove(s)
				self.space.remove(p.body)
				self.players.remove(p)
				return

def offsetBox(cx, cy, length, width):
	hl = length / 2
	hw = width / 2
	x1 = float(cx - hl)
	x2 = float(cx + hl)
	y1 = float(cy - hw)
	y2 = float(cy + hw)
	return [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]


@app.route('/')
def index():
	return render_template('index.html')

@app.route('/game')
def game():
	return render_template('game.html')

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

socketio = SocketIO(app)

@socketio.on('connect')
def on_connect():
	sid = request.sid
	room.createPlayer(sid)
	emit('hello', {'id': sid})

@socketio.on('disconnect')
def on_disconnect():
	sid = request.sid
	room.removePlayer(sid)

@socketio.on('direction')
def on_direction(data):
	player = room.player_by_sid(request.sid)
	player.rotation = data['angle']

@socketio.on('boost')
def on_boost(data):
	send('asdf')

@socketio.on('brake')
def on_boost(data):
	pass


if __name__ == '__main__':
	room = GameRoom([])
	webserver = threading.Thread(target=lambda: socketio.run(app, host='0.0.0.0'))
	webserver.start()
	while True:
		room.update(0.05, socketio)
		time.sleep(0.05)
