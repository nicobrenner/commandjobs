import asyncio
import os
import json

from openai import AsyncOpenAI
from dotenv import load_dotenv

class GPTProcessor:
    def __init__(self, db_manager, api_key):
        # Load environment variables
        load_dotenv()
        self.db_manager = db_manager
        self.client = AsyncOpenAI(api_key=api_key)
        self.log_file = 'gpt_processor.log'  # Log file path
        self.listings_per_batch = os.getenv('COMMANDJOBS_LISTINGS_PER_BATCH')
        if self.listings_per_batch  is None:
            raise ValueError(f"COMMANDJOBS_LISTINGS_PER_BATCH is not set; exiting.")

    def log(self, message):
        """Append a message to the log file."""
        with open(self.log_file, 'a') as f:
            f.write(f"{message}\n")

    async def process_job_listings_with_gpt(self, resume_path, update_ui_callback):
        update_ui_callback(f"Getting job listings")
        resume = self.read_resume_from_file(resume_path)
        job_listings = self.db_manager.fetch_job_listings(self.listings_per_batch)
        update_ui_callback(f"Processing {len(job_listings)} listings with AI. Please wait...")
        self.log(f"Creating tasks for {len(job_listings)} job listings")
        tasks = [self.process_single_listing(job_id, job_text, job_html, resume, update_ui_callback) for job_id, job_text, job_html in job_listings]
        self.log(f"About to 'gather' {len(tasks)} tasks")
        # Letting the exceptions bubble up to MenuApp
        await asyncio.gather(*tasks)

    async def process_single_listing(self, job_id, job_text, job_html, resume, update_ui_callback):
        prompt = self.generate_prompt(job_text, job_html, resume)
        self.log(f"Prompt: {prompt}")  # Log the prompt
        if not prompt:  # Check if prompt is None or empty
            raise ValueError("Prompt is None or empty, skipping GPT request.")
        
        answer_dict = {}
        # Letting bubble up the potential exceptions from
        # the two lines below, up to process_job_listings_with_gpt
        answer = await self.get_gpt_response(prompt)
        self.db_manager.save_gpt_interaction(job_id, prompt, answer)  
            
        # Attempt to load the JSON string into a Python dictionary
        try:
            answer_dict = json.loads(answer)
            # Show a little preview of the processed jobs
            update_ui_callback(f"Processed {answer_dict['company_name']} / {answer_dict['small_summary'][:50]}")
        except json.JSONDecodeError:
            self.log(f"Invalid JSON format: {answer}")
        
        self.log(f"Processed job_id: {job_id}")

    def read_resume_from_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return "Resume file not found."

    def generate_prompt(self, job_text, job_html, resume):
        # Similar to the original prompt creation logic
        # Ensure to return the formatted prompt string
        # output_format = """{
        #     "small_summary": "Wine and Open Source developers for C-language systems programming",
        #     "company_name": "CodeWeavers",
        #     "available_positions": [
        #         {
        #         "position": "Wine and General Open Source Developers",
        #         "link": "https://www.codeweavers.com/about/jobs"
        #         }
        #     ],
        #     "tech_stack_description": "C-language systems programming",
        #     "use_rails": "No",
        #     "use_python": "No",
        #     "remote_positions": "Yes",
        #     "hiring_in_us": "Yes",
        #     "how_to_apply": "Apply through our website, here is the link: https://www.codeweavers.com/about/jobs",
        #     "back_ground_with_priority": null,
        #     "fit_for_resume": "No",
        #     "fit_justification": "The position is for Wine and Open Source developers, neither of which the resume has experience with. The job is remote in the US"
        #     }"""
        output_format_str = os.getenv('COMMANDJOBS_OUTPUT_FORMAT')
        self.log(f"output_format_str: {output_format_str}") 
        # Convert the escaped newlines back to actual newline characters
        output_format = output_format_str.encode().decode('unicode_escape')
        # self.log(f"output_format: {output_format}") 
        roles = os.getenv('COMMANDJOBS_ROLE')
        job_requirement_exclusions=os.getenv('COMMANDJOBS_EXCLUSIONS')
        # self.log(f"job_requirement_exclusions: {job_requirement_exclusions}")
        ideal_job_questions_template = os.getenv('COMMANDJOBS_IDEAL_JOB_QUESTIONS')
        prompt_template = os.getenv('COMMANDJOBS_PROMPT')

        # Perform the interpolation
        ideal_job_questions = ideal_job_questions_template.format(job_requirement_exclusions=job_requirement_exclusions)
        prompt = prompt_template.format(job_html=job_html, resume=resume, roles=roles, ideal_job_questions=ideal_job_questions, output_format=output_format)

        return prompt

    async def get_gpt_response(self, prompt):
        response = await self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=os.getenv('OPENAI_GPT_MODEL'),
        )
        self.log(f"response.choices: {response.choices}")
        return response.choices[0].message.content

