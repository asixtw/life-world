import type { Persona, Scenario, SourceRef } from '../src/contracts' // JSON 是隔離的版本化示範資料。
import personaData from './personas.v1.json' // 固定十五位角色 ID。
import scenarioData from './scenarios.v1.json' // 六場各三條以上可達結尾路徑。
import sourceData from './sources.v1.json' // 所有來源附定位與人工核對狀態。

export const personas = personaData as Persona[] // 選角只讀示範資料。
export const scenarios = scenarioData as Scenario[] // 腳本不呼叫正式服務。
export const sources = sourceData as SourceRef[] // 來源目錄與劇情分離。
