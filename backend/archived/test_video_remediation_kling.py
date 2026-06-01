import os
import sys

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jusads_video_compliance.video_checker import VideoComplianceChecker
from jusads_video_compliance.video_remediator_kling import VideoRemediatorKling

def main():
    video_path = os.path.join("backend", "assets", "Test Video.mp4")
    market = "malaysia"
    ethnicity = "all"

    print("=" * 80)
    print(" END-TO-END VIDEO PIPELINE TEST (KLING AI EDITION)")
    print(f" Video: {video_path}")
    print(f" Target: {market.title()} | {ethnicity.title()}")
    print("=" * 80)

    # Step 1: Check compliance
    print("\n--- [Step 1] Running Compliance Check ---")
    checker = VideoComplianceChecker()
    compliance_result = checker.check_compliance(
        video_path=video_path,
        market=market,
        ethnicity=ethnicity,
    )
    
    if not compliance_result:
        print("Failed to run compliance check.")
        return

    print("\n[Compliance Result]")
    print(f"Transcript: {compliance_result.get('transcript_used')}")
    print(f"Explanation: {compliance_result.get('explanation')}")
    print(f"Suggestion: {compliance_result.get('suggestion')}")
    
    if not compliance_result.get("high_risk_indicators"):
        print("\nSUCCESS: Video is compliant! No remediation needed.")
        return
        
    print("\nHigh Risk Indicators Found:")
    for ind in compliance_result.get("high_risk_indicators", []):
        print(f"  - [{ind['timestamp']}] {ind['category']}: {ind['description']}")

    # Step 2: Remediate with Kling AI
    print("\n--- [Step 2] Running Kling Video Remediation ---")
    remediator = VideoRemediatorKling()
    remediation_result = remediator.remediate(
        video_path=video_path,
        compliance_result=compliance_result,
        market=market,
        ethnicity=ethnicity,
    )

    print("\n[Remediation Result]")
    print("Rewritten Script:")
    print(remediation_result.get('rewritten_script'))

    audio_path = remediation_result.get('generated_voiceover_path')
    if audio_path:
        print(f"\nGenerated Localized Voiceover:")
        print(f"  -> SUCCESS: Saved to {audio_path}")
        
    final_path = remediation_result.get('final_video_path')
    if final_path:
        print(f"\nFinal Assembled Video:")
        print(f"  -> SUCCESS: Saved to {final_path}")
        
    print("\nGenerated Kling AI Edits:")
    edits = remediation_result.get('video_edit_prompts', [])
    for idx, edit in enumerate(edits):
        print(f"  [{idx+1}] Timestamp: {edit.get('timestamp')}")
        print(f"      Prompt: {edit.get('prompt')}")
        print(f"      Reason: {edit.get('reason')}")
        vid_path = edit.get("generated_video_path")
        if vid_path:
            print(f"      -> SUCCESS: Saved to {vid_path}")
        else:
            print(f"      -> FAILED to generate Kling video edit for this prompt.")
            
    print("\nChanges Made:")
    for change in remediation_result.get('changes_made', []):
        print(f"  - {change}")

if __name__ == "__main__":
    main()
