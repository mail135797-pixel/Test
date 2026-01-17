/**
 * Yahoo! Shopping API Integration for JAN Code Fetching
 * 
 * Instructions:
 * 1. Open your Google Sheet.
 * 2. Go to Extensions > Apps Script.
 * 3. Paste this code into Code.gs.
 * 4. Set your YAHOO_APP_ID in script properties or hardcode below.
 * 5. Run 'init' to create the trigger (runs every 5 minutes).
 */

const YAHOO_APP_ID = "YOUR_YAHOO_CLIENT_ID_HERE"; // Replace with your ID or use PropertiesService
const SHEET_NAME = "Sheet1"; // Change if needed
const BATCH_SIZE = 10; // Number of items to process per execution

function init() {
  // Delete existing triggers
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'processBatch') {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  
  // Create new trigger: runs every 5 minutes
  ScriptApp.newTrigger('processBatch')
    .timeBased()
    .everyMinutes(5)
    .create();
    
  Logger.log("Trigger initialized. 'processBatch' will run every 5 minutes.");
}

function processBatch() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) {
    Logger.log("Sheet not found: " + SHEET_NAME);
    return;
  }
  
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  // Find column indices
  const titleIdx = headers.indexOf("Title");
  const janIdx = headers.indexOf("JAN Code");
  
  if (titleIdx === -1) {
    Logger.log("Title column not found");
    return;
  }
  
  // If JAN column doesn't exist, assume it's the last one or create it
  // This script assumes the structure matches the Excel file uploaded
  // A: Title, B: Link, C: Item Number, D: Price, E: JAN Code
  
  const startRow = getNextStartRow(sheet);
  if (startRow > data.length) {
    Logger.log("All rows processed.");
    return; // Done
  }
  
  let processedCount = 0;
  
  for (let i = startRow - 1; i < data.length; i++) {
    if (processedCount >= BATCH_SIZE) break;
    
    // Check if JAN is already filled
    const currentJan = data[i][janIdx];
    if (currentJan && currentJan.toString().trim() !== "") {
      continue;
    }
    
    const title = data[i][titleIdx];
    const jan = fetchJanFromYahoo(title);
    
    if (jan) {
      // Update cell (row is i + 1)
      sheet.getRange(i + 1, janIdx + 1).setValue(jan);
      Logger.log(`[Row ${i+1}] Found JAN for '${title}': ${jan}`);
    } else {
      Logger.log(`[Row ${i+1}] No JAN found for '${title}'`);
      // Mark as processed (e.g. set a flag or just leave blank, here we just move on)
      // To avoid reprocessing, we might need a status column, but for now we rely on JAN being empty
    }
    
    processedCount++;
    Utilities.sleep(1000); // 1 second delay
  }
  
  // Save the next start row for next time (optional if we just scan for empty JANs)
  // But scanning 8000 rows every time is slow. Better to use PropertiesService.
  setNextStartRow(startRow + processedCount);
}

function getNextStartRow(sheet) {
  const props = PropertiesService.getScriptProperties();
  const savedRow = props.getProperty("LAST_PROCESSED_ROW");
  if (savedRow) return parseInt(savedRow);
  return 2; // Start from row 2 (skipping header)
}

function setNextStartRow(row) {
  PropertiesService.getScriptProperties().setProperty("LAST_PROCESSED_ROW", row.toString());
}

function cleanTitle(title) {
  // 1. Remove 'Costco', 'コストコ'
  let cleaned = title.replace(/(Costco|コストコ)/gi, '');
  
  // 2. Remove weights/volumes/status
  // Simple regex for JS
  cleaned = cleaned.replace(/(\d+(\.\d+)?(kg|g|ml|L)|冷凍|冷蔵)/gi, '');
  
  // 3. Remove parentheses
  cleaned = cleaned.replace(/[\(\)（）]/g, ' ');
  
  // 4. Whitespace and keywords
  const parts = cleaned.trim().split(/\s+/);
  return parts.slice(0, 3).join(' ');
}

function fetchJanFromYahoo(title) {
  const appId = YAHOO_APP_ID;
  if (!appId || appId === "YOUR_YAHOO_CLIENT_ID_HERE") {
    Logger.log("App ID not set.");
    return null;
  }
  
  const cleanedTitle = cleanTitle(title);
  const query = `${cleanedTitle} コストコ`;
  const url = `https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch?appid=${appId}&query=${encodeURIComponent(query)}&results=10&sort=-score`;
  
  try {
    const response = UrlFetchApp.fetch(url, {muteHttpExceptions: true});
    const code = response.getResponseCode();
    
    if (code === 429) {
      Logger.log("Rate limited (429)");
      Utilities.sleep(5000);
      return null;
    }
    
    if (code !== 200) {
      Logger.log("API Error: " + code);
      return null;
    }
    
    const json = JSON.parse(response.getContentText());
    if (!json.hits || json.hits.length === 0) return null;
    
    // Fuzzy match logic is hard in pure GAS without libraries.
    // We'll use a simple token match heuristic or just take the top result if it has a JAN.
    
    for (const hit of json.hits) {
      if (hit.janCode) {
        // Optional: Add simple validation here (e.g. check if at least one keyword matches)
        return hit.janCode;
      }
    }
    
  } catch (e) {
    Logger.log("Fetch error: " + e.toString());
  }
  return null;
}
