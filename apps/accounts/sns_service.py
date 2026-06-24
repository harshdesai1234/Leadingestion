"""
AWS SNS Service for sending OTP via SMS
"""
import boto3
import os
from botocore.exceptions import ClientError
from django.conf import settings


class SNSService:
    """
    Service class for sending SMS messages via AWS SNS
    """
    
    def __init__(self):
        """
        Initialize the SNS client with AWS credentials from environment variables
        """
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize SNS client
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
    
    def send_otp(self, phone_number, otp):
        """
        Send OTP to the specified phone number via AWS SNS
        
        Args:
            phone_number (str): The phone number to send the OTP to (E.164 format recommended)
            otp (str): The OTP code to send
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            # Format the message
            message = f"Your Agentyne verification code is: {otp}. This code will expire in 10 minutes."
            
            # Ensure phone number is in E.164 format (starts with +)
            if not phone_number.startswith('+'):
                # If no country code, assume US (+1)
                phone_number = f"+1{phone_number}"
            
            # Send SMS via SNS
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': 'Agentyne'
                    },
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'  # Use 'Transactional' for OTP messages
                    }
                }
            )
            
            # Check if message was sent successfully
            if response.get('MessageId'):
                print(f"OTP sent successfully to {phone_number}. MessageId: {response['MessageId']}")
                return True
            else:
                print(f"Failed to send OTP to {phone_number}")
                return False
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"AWS SNS Error ({error_code}): {error_message}")
            return False
            
        except Exception as e:
            print(f"Error sending OTP via SNS: {str(e)}")
            return False
    
    def send_sms(self, phone_number, message):
        """
        Send a generic SMS message to the specified phone number
        
        Args:
            phone_number (str): The phone number to send the message to
            message (str): The message content
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            # Ensure phone number is in E.164 format
            if not phone_number.startswith('+'):
                phone_number = f"+1{phone_number}"
            
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message
            )
            
            if response.get('MessageId'):
                print(f"SMS sent successfully to {phone_number}. MessageId: {response['MessageId']}")
                return True
            else:
                print(f"Failed to send SMS to {phone_number}")
                return False
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"AWS SNS Error ({error_code}): {error_message}")
            return False
            
        except Exception as e:
            print(f"Error sending SMS via SNS: {str(e)}")
            return False
