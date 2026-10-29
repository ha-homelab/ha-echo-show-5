package com.msp1974.vacompanion.nearest

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun NearestSettingsPane(onBack: () -> Unit) {
    val context = LocalContext.current
    var saved by remember { mutableStateOf(NearestSettings.read(context)) }
    var enabled by remember { mutableStateOf(saved.enabled) }
    var name by remember { mutableStateOf(saved.name) }
    var word by remember { mutableStateOf("") }
    var window by remember { mutableStateOf(saved.windowMs.toString()) }
    var offset by remember { mutableStateOf(saved.offsetDb.toString()) }
    var message by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Nearest voice device", style = MaterialTheme.typography.titleLarge)
        Text("Devices sharing the same private house word elect one answer before starting Assist. Manual activation and ongoing replies stay local.")
        Row { Switch(enabled, { enabled = it }); Text(" Participate in room election") }
        OutlinedTextField(name, { name = it }, label = { Text("Unique device name") }, singleLine = true)
        OutlinedTextField(word, { word = it }, label = { Text("House word (new: 16+ characters; blank keeps saved word)") },
            visualTransformation = PasswordVisualTransformation(), singleLine = true)
        OutlinedTextField(window, { window = it }, label = { Text("Election window: 100–500 ms") }, singleLine = true)
        OutlinedTextField(offset, { offset = it }, label = { Text("Microphone offset: −30 to 30 dB") }, singleLine = true)
        Text("The house word stays in this app's private storage and is never displayed after saving. All participating devices must use exactly the same word.")
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = {
                try {
                    val value = NearestConfig(enabled, name.trim(), NearestConfig.houseWordFromInput(word, saved.houseWord),
                        window.toLong(), offset.toDouble(), saved.port)
                    NearestSettings.save(context, value)
                    saved = value; word = ""; message = "Saved. Voice election settings reloaded."
                } catch (_: Exception) { message = "Check the name, house word, window and offset." }
            }) { Text("Save") }
            OutlinedButton(onClick = onBack) { Text("Back") }
        }
        Text(message)
    }
}
