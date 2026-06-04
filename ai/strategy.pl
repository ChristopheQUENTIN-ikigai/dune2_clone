% ============================================================
% Dune 2 Clone — AI Strategy Knowledge Base
% Full strategic reasoning: build order, production, attack,
% target selection, economy vs military balance.
% ============================================================

% --- Dynamic facts asserted by Python ---
:- dynamic my_credits/1.
:- dynamic my_power/2.          % (used, total)
:- dynamic my_building/4.       % (type, x, y, health)
:- dynamic my_unit/4.           % (type, x, y, health)
:- dynamic enemy_building/4.
:- dynamic enemy_unit/4.
:- dynamic spice_field/3.       % (x, y, amount)
:- dynamic game_tick/1.
:- dynamic my_building_id/2.    % (type, entity_id)
:- dynamic my_unit_id/2.        % (type, entity_id)

% --- Counting helpers ---
count_my_buildings(Type, Count) :-
    findall(1, my_building(Type, _, _, _), L),
    length(L, Count).

count_my_units(Type, Count) :-
    findall(1, my_unit(Type, _, _, _), L),
    length(L, Count).

count_enemy_units(Count) :-
    findall(1, enemy_unit(_, _, _, _), L),
    length(L, Count).

count_enemy_buildings(Count) :-
    findall(1, enemy_building(_, _, _, _), L),
    length(L, Count).

total_my_army(Count) :-
    count_my_units(soldier, S),
    Count is S.

% --- Power management ---
power_ok :-
    my_power(Used, Total),
    Total >= Used.

need_power :-
    my_power(Used, Total),
    Total < Used + 20.

% --- Economy assessment ---
has_refinery :-
    my_building(refinery, _, _, _).

has_harvester :-
    my_unit(harvester, _, _, _).

economy_stable :-
    has_refinery,
    has_harvester,
    my_credits(C),
    C > 500.

economy_strong :-
    has_refinery,
    my_credits(C),
    C > 3000.

% --- Military assessment ---
army_weak :-
    total_my_army(A),
    A < 3.

army_moderate :-
    total_my_army(A),
    A >= 3,
    A < 8.

army_strong :-
    total_my_army(A),
    A >= 8.

outnumber_enemy :-
    total_my_army(My),
    count_enemy_units(Enemy),
    My > Enemy * 1.5.

% ============================================================
% BUILD ORDER DECISIONS
% Priority: Construction Yard > Refinery > Solar > Units
% ============================================================

% First priority: need barracks for soldiers
decision(build, barracks) :-
    \+ my_building(barracks, _, _, _),
    my_credits(C), C >= 400,
    count_my_buildings(construction_yard, CY), CY > 0.

% Need a refinery for economy
decision(build, refinery) :-
    \+ has_refinery,
    my_credits(C), C >= 1500,
    count_my_buildings(construction_yard, CY), CY > 0.

% Need power before expanding
decision(build, solar_plant) :-
    need_power,
    my_credits(C), C >= 500,
    count_my_buildings(construction_yard, CY), CY > 0.

% Second refinery if rich
decision(build, refinery) :-
    economy_strong,
    count_my_buildings(refinery, R), R < 2,
    my_credits(C), C >= 1500,
    count_my_buildings(construction_yard, CY), CY > 0.

% ============================================================
% UNIT PRODUCTION DECISIONS
% ============================================================

% Always need at least one harvester
decision(produce, harvester) :-
    has_refinery,
    \+ has_harvester,
    my_credits(C), C >= 500.

% Produce soldiers only if barracks exists
decision(produce, soldier) :-
    my_building(barracks, _, _, _),
    my_credits(C), C >= 60,
    total_my_army(A), A < 15.

% Prioritize more soldiers when threatened (requires barracks)
decision(produce_priority, soldier) :-
    my_building(barracks, _, _, _),
    count_enemy_units(E), E > 0,
    army_weak,
    my_credits(C), C >= 60.

% Replace harvester if lost
decision(produce, harvester) :-
    has_refinery,
    count_my_units(harvester, H), H < 1,
    my_credits(C), C >= 500.

% ============================================================
% ATTACK DECISIONS
% ============================================================

% Attack when we outnumber the enemy
decision(attack, all) :-
    army_strong,
    outnumber_enemy,
    count_enemy_buildings(EB), EB > 0.

% Aggressive attack when very strong
decision(attack, all) :-
    total_my_army(A), A >= 12,
    count_enemy_buildings(EB), EB > 0.

% Defensive attack nearby enemies
decision(defend, base) :-
    enemy_unit(_, EX, EY, _),
    my_building(_, BX, BY, _),
    DX is abs(EX - BX),
    DY is abs(EY - BY),
    DX < 15, DY < 15.

% ============================================================
% TARGET SELECTION
% ============================================================

% Attack nearest enemy unit
best_target(unit, X, Y) :-
    my_building(_, BX, BY, _),
    findall(D-ex(EX,EY), (
        enemy_unit(_, EX, EY, _),
        D is abs(EX - BX) + abs(EY - BY)
    ), Targets),
    Targets \= [],
    sort(Targets, [_-ex(X,Y)|_]).

% Attack enemy buildings if no units nearby
best_target(building, X, Y) :-
    \+ enemy_unit(_, _, _, _),
    enemy_building(_, X, Y, _).

% Attack weakest enemy building
best_target(building, X, Y) :-
    findall(H-bld(BX,BY), (
        enemy_building(_, BX, BY, H)
    ), Buildings),
    Buildings \= [],
    sort(Buildings, [_-bld(X,Y)|_]).

% ============================================================
% STRATEGIC BALANCE
% ============================================================

% Overall strategy: economy first, then military
strategy(economy) :-
    \+ economy_stable.

strategy(expand) :-
    economy_strong,
    count_my_buildings(refinery, R), R < 2.

strategy(military) :-
    economy_stable,
    army_weak.

strategy(attack) :-
    economy_stable,
    army_strong.

strategy(defend) :-
    decision(defend, base).

% Get all current decisions
all_decisions(Decisions) :-
    findall(D, decision(_, D), Decisions).

% Get strategy recommendation
recommend_strategy(S) :-
    strategy(S), !.
recommend_strategy(military).  % Default
