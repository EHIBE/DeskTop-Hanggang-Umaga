import test, { mock } from 'node:test'
import assert from 'node:assert/strict'
import { GameSocket, type SocketStatus } from '../src/renderer/src/lib/socket'
import type { ServerMessage } from '../src/renderer/src/lib/types'
import { installWindow } from './helpers'

class FakeWebSocket {
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = 0
  sent: string[] = []
  closed = 0
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  url: string
  protocols: readonly string[]
  constructor(url: string, protocols: readonly string[]) {
    this.url = url
    this.protocols = protocols
    FakeWebSocket.instances.push(this)
  }
  send(data: string): void {
    this.sent.push(data)
  }
  close(): void {
    this.closed += 1
  }
  open(): void {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }
  receive(data: unknown): void {
    this.onmessage?.({ data })
  }
  drop(): void {
    this.readyState = 3
    this.onclose?.()
  }
}

let config: () => Promise<{ port: number; token: string }>

function setup(): void {
  FakeWebSocket.instances = []
  config = () => Promise.resolve({ port: 4321, token: 'tok' })
  installWindow({ desktop: { getConfig: () => config() } })
  Reflect.set(globalThis, 'WebSocket', FakeWebSocket)
}

async function flush(): Promise<void> {
  for (let turn = 0; turn < 5; turn += 1) await new Promise((resolve) => setImmediate(resolve))
}

function latest(): FakeWebSocket {
  const socket = FakeWebSocket.instances.at(-1)
  assert.ok(socket)
  return socket
}

const KNOWN_TYPES = [
  'state',
  'devices',
  'campaigns',
  'frame',
  'notice',
  'card',
  'sprite',
  'cost',
  'events',
  'narration',
  'caption',
  'summon.result',
  'settings',
  'map',
  'crops',
  'moment',
  'recap'
]

test('connects to loopback with the desktop subprotocol and the token', async () => {
  setup()
  const socket = new GameSocket()
  socket.start()
  await flush()
  assert.equal(latest().url, 'ws://127.0.0.1:4321/ws')
  assert.deepEqual(latest().protocols, ['desktop', 'tok'])
  assert.equal(socket.status, 'connecting')
  latest().open()
  assert.equal(socket.status, 'open')
  socket.stop()
})

test('start twice opens only one connection', async () => {
  setup()
  const socket = new GameSocket()
  socket.start()
  socket.start()
  await flush()
  assert.equal(FakeWebSocket.instances.length, 1)
  socket.stop()
})

test('delivers every known server type and drops everything else', async () => {
  setup()
  const socket = new GameSocket()
  const got: ServerMessage[] = []
  socket.subscribe((message) => got.push(message))
  socket.start()
  await flush()
  latest().open()
  for (const type of KNOWN_TYPES) latest().receive(JSON.stringify({ type, seq: 1 }))
  assert.deepEqual(
    got.map((message) => message.type),
    KNOWN_TYPES
  )
  got.length = 0
  const junk = [
    JSON.stringify({ type: 'bogus' }),
    JSON.stringify({ type: 5 }),
    JSON.stringify({}),
    JSON.stringify(null),
    JSON.stringify([1, 2]),
    JSON.stringify('state'),
    JSON.stringify(7),
    '{not json',
    '',
    new ArrayBuffer(4),
    null,
    undefined
  ]
  for (const raw of junk) latest().receive(raw)
  assert.equal(got.length, 0)
  socket.stop()
})

test('unsubscribe stops delivery', async () => {
  setup()
  const socket = new GameSocket()
  let count = 0
  const off = socket.subscribe(() => (count += 1))
  socket.start()
  await flush()
  latest().open()
  latest().receive(JSON.stringify({ type: 'state' }))
  off()
  latest().receive(JSON.stringify({ type: 'state' }))
  assert.equal(count, 1)
  socket.stop()
})

test('send serializes while open and reports false otherwise', async () => {
  setup()
  const socket = new GameSocket()
  assert.equal(socket.send({ type: 'end_turn' }), false)
  socket.start()
  await flush()
  assert.equal(socket.send({ type: 'end_turn' }), false)
  latest().open()
  assert.equal(socket.send({ type: 'ptt', down: true }), true)
  assert.deepEqual(latest().sent, ['{"type":"ptt","down":true}'])
  latest().drop()
  assert.equal(socket.send({ type: 'end_turn' }), false)
  socket.stop()
})

test('status listeners hear connecting, open and closed without repeats', async () => {
  setup()
  const socket = new GameSocket()
  const seen: SocketStatus[] = []
  socket.onStatus((status) => seen.push(status))
  socket.start()
  await flush()
  latest().open()
  socket.stop()
  socket.stop()
  assert.deepEqual(seen, ['open', 'closed'])
})

test('reconnect backs off 500, 1000, 2000, 5000 and holds at 5000', async () => {
  setup()
  mock.timers.enable({ apis: ['setTimeout'] })
  const delays: number[] = []
  const realSetTimeout = globalThis.setTimeout
  Reflect.set(globalThis, 'setTimeout', (fn: () => void, ms: number) => {
    delays.push(ms)
    return realSetTimeout(fn, ms)
  })
  const socket = new GameSocket()
  socket.start()
  await flush()
  for (let round = 0; round < 6; round += 1) {
    const before = FakeWebSocket.instances.length
    latest().drop()
    mock.timers.tick(5000)
    await flush()
    assert.equal(FakeWebSocket.instances.length, before + 1)
  }
  assert.deepEqual(delays, [500, 1000, 2000, 5000, 5000, 5000])
  socket.stop()
  Reflect.set(globalThis, 'setTimeout', realSetTimeout)
  mock.timers.reset()
})

test('a successful open resets the backoff', async () => {
  setup()
  mock.timers.enable({ apis: ['setTimeout'] })
  const delays: number[] = []
  const realSetTimeout = globalThis.setTimeout
  Reflect.set(globalThis, 'setTimeout', (fn: () => void, ms: number) => {
    delays.push(ms)
    return realSetTimeout(fn, ms)
  })
  const socket = new GameSocket()
  socket.start()
  await flush()
  latest().drop()
  mock.timers.tick(5000)
  await flush()
  latest().open()
  latest().drop()
  assert.deepEqual(delays, [500, 500])
  socket.stop()
  Reflect.set(globalThis, 'setTimeout', realSetTimeout)
  mock.timers.reset()
})

test('stop cancels reconnects and detaches handlers', async () => {
  setup()
  mock.timers.enable({ apis: ['setTimeout'] })
  const socket = new GameSocket()
  socket.start()
  await flush()
  const first = latest()
  first.drop()
  socket.stop()
  mock.timers.tick(10000)
  await flush()
  assert.equal(FakeWebSocket.instances.length, 1)
  assert.equal(socket.status, 'closed')
  mock.timers.reset()

  setup()
  const second = new GameSocket()
  second.start()
  await flush()
  const live = latest()
  second.stop()
  assert.equal(live.closed, 1)
  assert.equal(live.onmessage, null)
  assert.equal(live.onclose, null)
})

test('a config failure marks the socket closed and keeps retrying', async () => {
  setup()
  mock.timers.enable({ apis: ['setTimeout'] })
  config = () => Promise.reject(new Error('no config'))
  const socket = new GameSocket()
  socket.start()
  await flush()
  assert.equal(socket.status, 'closed')
  config = () => Promise.resolve({ port: 1, token: 't' })
  mock.timers.tick(500)
  await flush()
  assert.equal(FakeWebSocket.instances.length, 1)
  socket.stop()
  mock.timers.reset()
})

test('socket errors close the connection', async () => {
  setup()
  const socket = new GameSocket()
  socket.start()
  await flush()
  latest().onerror?.()
  assert.equal(latest().closed, 1)
  socket.stop()
})
