import asyncio
import logging
import sys
import helper
from os import getenv
from typing import Any, Dict
from dotenv import load_dotenv

from redis.commands.json.path import Path
from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButtonRequestUser
)
from aiogram.methods.send_message import SendMessage

import redis

load_dotenv()
TOKEN = getenv("BOT_TOKEN")
host = getenv('REDIS_HOST')
port = getenv('REDIS_PORT')
password = getenv('REDIS_PASSWORD')

form_router = Router()

redis_conn = redis.Redis(
  host=host,
  port=port,
  password=password)
# storage = RedisStorage(redis_conn, key_builder=DefaultKeyBuilder(with_destiny=True))

class RegisterForm(StatesGroup):
    name = State()
    username = State()
    user_type = State()
    
class HailForm(StatesGroup):
    curr_location = State()
    dest_location = State()
    confirm = State()
    driver_id = State()
    passenger_id = State()
    ride_key = State()
    
class RatingForm(StatesGroup):
    rating = State()
    comment = State()
    ride_id = State()
    driver_id = State()

@form_router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    user_id = state.key.user_id
    
    print('user: ', user_id)
    pattern = f'Passenger:{user_id}:profile'
    dr = f'Driver:{user_id}:profile'
    res_ = redis_conn.keys(f'Passenger:{user_id}:profile')
    res2_ = redis_conn.keys(f'Driver:{user_id}:profile')
    
    # print('res: ', pattern, res)
    
    # Check if user already registered or not
    if not res_ and not res2_:
        await message.answer('Welcome new user, please follow the steps to register!')
        await state.set_state(RegisterForm.name)
        await message.answer('Please enter your name?', reply_markup=ReplyKeyboardRemove())
    else:
        res = redis_conn.get(pattern)
        res2 = redis_conn.get(dr)
        print('bef: ', res, type(res))
        print('bef2: ', res2, type(res2))
        # res = res.decode('utf-8')
        # res = res.replace("'", '"')
        # import ast
        
        if res_:
            print('here: ', res)
            res = helper.string_to_dict(res)
            
        if res2_:
            print('here res2: ', res2)
            res2 = helper.string_to_dict(res2)
        print('res: ', res, type(res))
        
        username = res['username'] if res else res2['username']
        await display_dashboard(message, f"Welcome {username}", res['user_type'] if res else res2['user_type'])
    
    
@form_router.message(RegisterForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text
    
    # save name to state
    await state.update_data(name=name)
    await state.set_state(RegisterForm.user_type)
    await message.answer(f'Hello {name}, what role are you taking: ', 
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text='Driver'),
                                     KeyboardButton(text='Passenger'),
                                 ]
                             ],
                             resize_keyboard=True
                         )
                         )
    
@form_router.message(RegisterForm.user_type)
async def process_user_type(message: Message, state: FSMContext) -> None:
    user_type = message.text
    
    await state.update_data(user_type=user_type)
    await state.set_state(RegisterForm.username)
    
    await message.answer('Enter a username: ')
    
@form_router.message(RegisterForm.username)
async def process_username(message: Message, state: FSMContext) -> None:
    username = message.text
    
    # check if username is already in use
    username_already_in_use = redis_conn.exists(f'username:{username}')
    
    print('user in use: ', username_already_in_use)
    
    # save username to state
    await state.update_data(username=username)
    print('handle user: ', username)
    
    # save the state to redis
    user_id = state.key.user_id
    
    new_user_data = await state.get_data()
    print('user: ', new_user_data)
    temp_username = new_user_data['username']
    
    # store the new user into redis
    user_type = new_user_data['user_type']
    new_user_data = str(new_user_data)
    print('new user: ', new_user_data, type(new_user_data))
    redis_conn.set(f'{user_type}:{user_id}:profile', new_user_data)
    
    await state.clear()
    
    await display_dashboard(message, f'Welcome {temp_username}', user_type)
    
@form_router.message(Command("history"))
@form_router.message(F.text.casefold() == 'history')
async def ride_history(message: Message, state: FSMContext) -> None:
    user_id = state.key.user_id
    
    key = f'Passenger:{user_id}:ride:*'
    print('key: ', key)
    
    history_keys = redis_conn.keys(key)
    
    history = []
    for his_key in history_keys:
        history.append(redis_conn.get(his_key.decode('utf-8')))
    
    print('his: ', history)
    
    text = 'Ride History\n\n'
    for his in history:
        his = helper.string_to_dict(his)
        print('his; ', his)
        text += f"Source: {his['curr_location']}\n"
        text += f"Destination: {his['dest_location']}\n"
        text += f"Date/Time: {his['datetime']}\n\n"
        
    print('ride hsi: ', text)
    
    await display_dashboard(message, text)
    
@form_router.message(Command("hail"))
@form_router.message(F.text.casefold() == "hail")
async def hail_ride(message: Message, state: FSMContext) -> None:
    # print('CANCELLLLLLEEEDD!!!')
    await state.set_state(HailForm.curr_location)
    
    await message.answer('Enter your location: ', reply_markup=ReplyKeyboardRemove())
    
@form_router.message(HailForm.curr_location)
async def process_current_location(message: Message, state: FSMContext) -> None:
    # add curr location to state
    curr_loc = message.text
    await state.update_data(curr_location=curr_loc)
    await state.set_state(HailForm.dest_location)
    
    await message.answer('Enter destination: ')
    
@form_router.message(HailForm.dest_location)
async def process_destination_location(message: Message, state: FSMContext) -> None:
    # add dest loc to state
    dest_loc = message.text
    await state.update_data(dest_location=dest_loc)
    
    new_hail_data = await state.get_data()
    est_time = 30
    
    message_to_send = ''
    message_to_send += f"Current location: {new_hail_data['curr_location']}\n"
    message_to_send += f"Destination: {new_hail_data['dest_location']}\n"
    message_to_send += f"Estimated time: {est_time} mins.\n\n"
    message_to_send += 'Please check the info. and confirm'
    
    await state.set_state(HailForm.confirm)
    
    await message.answer(message_to_send, 
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text='Confirm'),
                                     KeyboardButton(text='Cancel'),
                                 ]
                             ],
                             resize_keyboard=True
                         )
                         )
    
@form_router.message(HailForm.confirm, F.text.casefold() == 'confirm')
async def confirm_hail_ride(message: Message, state: FSMContext) -> None:
    from datetime import datetime
    
    new_hail_data = await state.get_data()
    new_hail_data['datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = state.key.user_id
    
    import uuid
    _id = str(uuid.uuid4()).replace('-', '')
    
    ride_key = f'Passenger:{user_id}:ride:{_id}'
    redis_conn.set(ride_key, str(new_hail_data))
    
    await state.update_data(passenger_id=user_id)
    await state.update_data(ride_key=ride_key)
    
    # await state.set_state(HailForm.driver_id)
    await state.clear()
    
    tele_bot = Bot(token=TOKEN)
    drivers = helper.get_driver_ids(redis_conn)
    
    passenger_location = new_hail_data['curr_location']
    message_to_driver = f'Passenger found at {passenger_location}\n/accept_ride_{_id}_{user_id}'
    for driver_id in drivers:
        await tele_bot.send_message(driver_id, message_to_driver)
    
    await message.answer('Waiting for a driver to accept your hail!', 
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text='Cancel Ride')
                                 ]
                             ],
                             resize_keyboard=True
                         )
    )
    
@form_router.message(F.text.split('_')[0] == '/accept' and F.text.split('_')[1] == 'ride')
async def driver_accept_ride(message: Message, state: FSMContext) -> None:
    states = await state.get_data()
    _id, user_id = message.text.split('_')[2], message.text.split('_')[3]
    
    ride_key = f'Passenger:{user_id}:ride:{_id}'
    
    ride_info = redis_conn.get(ride_key)
    ride_info_dict = helper.string_to_dict(ride_info)
    
    if 'driver_id' in ride_info_dict:
        await message.answer('Ride already accepted by another driver')
    else:
        ride_info_dict['driver_id'] = state.key.user_id
        redis_conn.set(ride_key, str(ride_info_dict))
        
        driver_key = f'Driver:{state.key.user_id}:profile'
        driver_profile = redis_conn.get(driver_key)
        driver_profile = helper.string_to_dict(driver_profile)
        driver_name = driver_profile['name']
        
        bot = Bot(token=TOKEN)
        
        # ride_key = f'Passenger:{user_id}:ride:{_id}'
        
        text_to_passenger = f'Ride accepted!! Please wait 20 minutes.\nDriver name: {driver_name}\n\n'
        # driver_id, passenger_id, ride_id
        text_to_passenger += f'To finish ride and give review to driver: /rate_driver_{state.key.user_id}_{user_id}_{_id}\n'
        # passenger_id, ride_id
        text_to_passenger += f'To cancel the ride: /cancel_ride_{user_id}_{_id}_{state.key.user_id}'
        await bot.send_message(user_id, text_to_passenger, reply_markup=ReplyKeyboardRemove())
        
        await state.clear()
        
        await message.answer('Ride accepted!!', reply_markup=ReplyKeyboardRemove())
    
# @form_router.message(HailForm.driver_id)
@form_router.message(F.text.casefold().len() == 5 and F.text.casefold().split('_')[0] == '/cancel' and F.text.casefold().split('_')[1] == 'ride')
async def cancel_ride(message: Message, state: FSMContext) -> None:
    print('cancel ride: ', message.text)
    # passenger_id, ride_id, driver_id
    passenger_id, ride_id, driver_id = message.text.split('_')[2], message.text.split('_')[3], message.text.split('_')[4]
    
    ride_key = f'Passenger:{passenger_id}:ride:{ride_id}'
    # delete the ride from redis
    redis_conn.delete(ride_key)
    
    await state.clear()
    
    bot = Bot(token=TOKEN)
    await bot.send_message(driver_id, 'Ride cancelled by passenger!', reply_markup=ReplyKeyboardRemove())
    
    await message.answer('Ride cancelled!!', reply_markup=ReplyKeyboardRemove())
    
# @form_router.message(HailForm.driver_id)
    
@form_router.message(F.text.casefold().len() >= 2 and F.text.casefold().split('_')[0] == '/rate' and F.text.casefold().split('_')[1] == 'driver')
async def process_rating(message: Message, state: FSMContext):
    # driver_id, passenger_id, ride_id
    print('process_rating: ')
    _, _, driver_id, passenger_id, ride_id = message.text.split('_')
    await state.update_data(ride_id=ride_id)
    await state.update_data(driver_id=driver_id)
    await state.set_state(RatingForm.rating)
    
    
    await message.answer('Enter your rating: ', reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='1'), KeyboardButton(text='2'),
                  KeyboardButton(text='3'), KeyboardButton(text='4')]],
        resize_keyboard=True
    ))
    
@form_router.message(RatingForm.rating)
async def add_driver_rating(message: Message, state: FSMContext) -> None:
    rating_num = message.text
    await state.update_data(rating=rating_num)
    
    rating_data = await state.get_data()
    ride_id, passenger_id, driver_id = rating_data['ride_id'], state.key.user_id, rating_data['driver_id']
    
    rating_data['rating'] = rating_num
    
    rate_key = f'Driver:{driver_id}:rating:{ride_id}'
    
    redis_conn.set(rate_key, str(rating_data))
    
    bot = Bot(token=TOKEN)
    
    await bot.send_message(driver_id, f'Passenger has given you rating of {rating_num}', reply_markup=ReplyKeyboardRemove())
    
    await state.clear()
    
    await display_dashboard(message, 'Thanks for your participation.', 'Passenger')
    
@form_router.message(HailForm.confirm, F.text.casefold() == 'cancel')
async def cancel_hail_ride(message: Message, state: FSMContext) -> None:
    await state.clear()
    
    await display_dashboard(message, 'Ride hail cancelled!!', 'Passenger')
    
@form_router.message(F.text.casefold() == 'Ride cancelled by passenger!')
async def driver_side_ride_cancelled_by_passenger(message: Message, state: FSMContext) -> None:
    await display_dashboard(message, 'Dashboard', 'Driver')
    
@form_router.message(F.text.casefold() == 'Driving History')
async def driver_history(message: Message, state: FSMContext) -> None:
    driver_id = state.key.user_id
    
    driver_key = f'Driver:{driver_id}:profile'
    driver_profile = redis_conn.get(driver_key)
    
    if driver_profile:
        driver_profile = helper.string_to_dict(driver_profile)
        text = f"Name: {driver_profile['name']}\n"
        text += f"Username: {driver_profile['username']}\n"
        text += f"User Type: {driver_profile['user_type']}\n"
        text += f"Rating: {driver_profile['rating']}\n"
        text += f"Number of rides: {driver_profile['num_rides']}\n"

async def display_dashboard(message: Message, text_to_view: str, user_type: str = 'Passenger') -> None:
    keyboards = []
    if user_type == 'Passenger':
        keyboards += [KeyboardButton(text='Hail'), KeyboardButton(text='History')]
    if user_type == 'Driver':
        keyboards += [KeyboardButton(text='Driving History')]
        
    keyboards += [KeyboardButton(text='Edit Profile')]
    
    await message.answer(text_to_view, 
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 keyboards
                             ],
                             resize_keyboard=True
                         ))


async def main():
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(form_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())