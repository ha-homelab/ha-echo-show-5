"""Test source-defined auth/room behavior offline without a fake HA installation."""
import ast
import asyncio
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components/show5_intercom"


def extract(filename, name, namespace):
    tree=ast.parse((ROOT/filename).read_text())
    node=next(n for n in tree.body if getattr(n,"name",None)==name)
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        node.decorator_list=[]
    code=compile(ast.Module(body=[node],type_ignores=[]), str(ROOT/filename), "exec")
    exec(code,namespace)
    return namespace[name]


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.backend=types.SimpleNamespace(config={"mute_entity":"switch.test"})
        self.hass=types.SimpleNamespace(data={"show5_intercom":self.backend})
        self.check=extract("__init__.py","backend_for",{"DOMAIN":"show5_intercom","POLICY_CONTROL":"control"})
    def connection(self,admin,allowed):
        permissions=types.SimpleNamespace(check_entity=lambda entity,policy:allowed)
        return types.SimpleNamespace(user=types.SimpleNamespace(is_admin=admin,permissions=permissions))
    def test_nonadmin_with_entity_control_denied(self):
        with self.assertRaises(ValueError):self.check(self.hass,self.connection(False,True))
    def test_admin_without_target_control_denied(self):
        with self.assertRaises(ValueError):self.check(self.hass,self.connection(True,False))
    def test_admin_target_control_allowed(self):
        self.assertIs(self.check(self.hass,self.connection(True,True)),self.backend)
    def test_unauthenticated_denied(self):
        with self.assertRaises(ValueError):self.check(self.hass,types.SimpleNamespace(user=None))
    def test_all_ws_commands_check_auth(self):
        for filename in ("__init__.py","room.py"):
            tree=ast.parse((ROOT/filename).read_text())
            for node in tree.body:
                if not isinstance(node,ast.AsyncFunctionDef) or not any("websocket_command" in ast.unparse(d) for d in node.decorator_list):continue
                calls=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="backend_for"]
                self.assertTrue(calls,node.name)
    def test_service_calls_carry_context(self):
        tree=ast.parse((ROOT/"__init__.py").read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="async_call"]
        self.assertEqual(len(calls),2)
        for call in calls:self.assertIn("context",{kw.arg for kw in call.keywords})


class RoomTests(unittest.IsolatedAsyncioTestCase):
    def room(self,fail):
        async def end(token,owner):
            if fail[0]:raise RuntimeError("restore failed")
        backend=types.SimpleNamespace(guard=types.SimpleNamespace(end=end))
        Room=extract("room.py","Room",{"asyncio":asyncio})
        room=Room(None,backend);room.call={"lease":"token","owner":"owner"}
        return room
    async def test_failed_restore_retains_call_for_retry(self):
        fail=[True];room=self.room(fail)
        with self.assertRaises(RuntimeError):await room.finish()
        self.assertEqual(room.call["lease"],"token")
        fail[0]=False;await room.finish();self.assertIsNone(room.call)
    async def test_disconnected_peer_removed_even_when_restore_fails(self):
        room=self.room([True]);connection=types.SimpleNamespace(send_event=lambda *args:None)
        membership=(connection,1,"a"*32)
        room.peers["show"]=membership
        with self.assertRaises(RuntimeError):await room.leave("show",membership)
        self.assertNotIn("show",room.peers);self.assertIsNotNone(room.call)
    async def test_stale_subscription_leave_preserves_same_connection_replacement(self):
        room=self.room([False]);events=[]
        connection=types.SimpleNamespace(send_event=lambda *args:events.append(args))
        old=(connection,1,"a"*32);new=(connection,2,"b"*32)
        room.peers["show"]=old
        async with room.lock:
            leaving=asyncio.create_task(room.leave("show",old))
            await asyncio.sleep(0)
            room.peers["show"]=new
        await leaving
        self.assertEqual(room.peers["show"],new)
        self.assertIsNotNone(room.call);self.assertEqual(events,[])
    async def test_stale_membership_end_cannot_finish_replacement_call(self):
        room=self.room([False]);connection=types.SimpleNamespace(send_event=lambda *args:None)
        room.peers["show"]=(connection,2,"b"*32)
        backend=types.SimpleNamespace(room=room)
        async def reply(connection,msg,operation):return await operation()
        action=extract("room.py","action",{"backend_for":lambda *args:backend,"reply":reply})
        with self.assertRaises(ValueError):
            await action(None,connection,{"action":"end","peer_id":"a"*32})
        self.assertIsNotNone(room.call)
        await action(None,connection,{"action":"end","peer_id":"b"*32})
        self.assertIsNone(room.call)
    async def test_membership_rejects_other_connection_even_with_same_peer_id(self):
        room=self.room([False]);connection=object()
        room.peers["show"]=(connection,1,"a"*32)
        self.assertEqual(room.role(connection,"a"*32),"show")
        with self.assertRaises(ValueError):room.role(object(),"a"*32)
    async def test_restored_event_waits_for_successful_cleanup(self):
        fail=[True];room=self.room(fail);events=[]
        connection=types.SimpleNamespace(send_event=lambda message_id,event:events.append(event["event"]))
        room.peers["caller"]=(connection,1,"a"*32)
        with self.assertRaises(RuntimeError):await room.finish()
        self.assertEqual(events,["ended"])
        fail[0]=False;await room.finish()
        self.assertEqual(events,["ended","ended","restored"])


if __name__ == "__main__":unittest.main()
